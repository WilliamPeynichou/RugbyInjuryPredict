import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from rugby_risk.http.store import FetchResult, RawStore
from rugby_risk.http.urls import canonicalize_url

pytestmark = pytest.mark.integration
REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES = REPO / "tests" / "fixtures"
WR_BASE = "https://api.wr-rims-prod.pulselive.com/rugby/v3/match"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/rugby/164205/summary"


def _put(store, source, url, path):
    content = path.read_bytes()
    store.put(
        FetchResult(
            source,
            canonicalize_url(url),
            200,
            content,
            "application/json",
            hashlib.sha256(content).hexdigest(),
            datetime(2025, 1, 1, tzinfo=UTC),
            False,
        )
    )


def _seed(tmp_path):
    store = RawStore(tmp_path / "data" / "raw")
    for name in ("six_nations", "november_test", "rwc", "incomplete"):
        _put(
            store,
            "worldrugby",
            f"{WR_BASE}/alt-{name}/summary",
            FIXTURES / "worldrugby" / f"{name}_summary.json",
        )
        timeline = FIXTURES / "worldrugby" / f"{name}_timeline.json"
        if timeline.exists():
            _put(store, "worldrugby", f"{WR_BASE}/alt-{name}/timeline", timeline)
    _put(store, "espn", f"{ESPN_BASE}?event=900001", FIXTURES / "espn" / "rwc_summary.json")
    _put(store, "espn", f"{ESPN_BASE}?event=900002", FIXTURES / "espn" / "incomplete_summary.json")


def _materialize(select, tmp_path):
    env = dict(os.environ, PYTHONPATH=f"{REPO}:{REPO / 'src'}", DATA_DIR=str(tmp_path / "data"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dagster",
            "asset",
            "materialize",
            "--select",
            select,
            "--partition",
            "2023-2024",
            "--module-name",
            "orchestration.definitions",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def _staging(tmp_path, entity, source):
    return pl.read_parquet(
        tmp_path
        / "data"
        / "staging"
        / entity
        / f"source={source}"
        / "season=2023-2024"
        / "part.parquet"
    )


def test_intl_assets_idempotent_and_report(tmp_path):
    _seed(tmp_path)
    _materialize("intl_staging_worldrugby", tmp_path)
    first = _staging(tmp_path, "appearance", "worldrugby")
    _materialize("intl_staging_worldrugby", tmp_path)
    assert _staging(tmp_path, "appearance", "worldrugby").equals(first)  # idempotence
    matches = _staging(tmp_path, "match", "worldrugby")
    assert sorted(matches["competition_code"].to_list()) == [
        "RWC",
        "SIX_NATIONS",
    ]  # novembre = 2024-2025
    _materialize("intl_staging_espn", tmp_path)
    assert _staging(tmp_path, "match", "espn").height == 1  # incomplet en quarantaine
    _materialize("intl_minutes_check", tmp_path)
    report = pl.read_parquet(
        tmp_path / "data" / "staging" / "_reports" / "intl_minutes" / "season=2023-2024.parquet"
    )
    flagged = report.filter(pl.col("flagged")).sort("team_name")
    assert flagged["team_name"].to_list() == ["France", "New Zealand"]
    france, nzl = flagged.row(0, named=True), flagged.row(1, named=True)
    assert france["minutes"] == 1130 and france["espn_players"] == 23  # rouge 10' : écart > 5 %
    assert nzl["minutes"] == 1200 and nzl["espn_players"] == 22  # un remplaçant de moins chez ESPN
