import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from rugby_risk.http.store import FetchResult, RawStore
from rugby_risk.http.urls import canonicalize_url
from rugby_risk.staging_schemas import SCHEMAS

REPO = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "allrugby"
SEASON_URL = "https://www.allrugby.com/saison-2023-2024/matchs"


def _seed_lake(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = RawStore(data_dir / "raw")
    pages = {
        "match_standard.html": f"{SEASON_URL}/bayonne-bordeaux-19357.html",
        "match_reentry_no_venue.html": f"{SEASON_URL}/bayonne-toulouse-19238.html",
        "match_final_yellow.html": f"{SEASON_URL}/toulouse-bordeaux-21156.html",
        # autre saison + Pro D2 : ignorée par le filtre de saison de la partition
        "match_prod2_red.html": "https://www.allrugby.com/saison-2021-2022/matchs/montauban-bayonne-14708.html",
        "player_jiff.html": "https://www.allrugby.com/joueurs/baptiste-heguy-5427.html",
        "player_non_jiff.html": "https://www.allrugby.com/joueurs/adam-coleman-5005.html",
    }
    for file, url in pages.items():
        content = (FIXTURES / file).read_bytes()
        store.put(
            FetchResult(
                "allrugby",
                canonicalize_url(url),
                200,
                content,
                "text/html",
                __import__("hashlib").sha256(content).hexdigest(),
                datetime(2025, 1, 1, tzinfo=UTC),
                False,
                None,
                None,
            )
        )
    return store


def _materialize(select, tmp_path=None):
    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp())
    env = dict(os.environ, PYTHONPATH=f"{REPO}:{REPO / 'src'}", DATA_DIR=str(tmp_path / "data"))
    return subprocess.run(
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


def test_staging_assets_offline_and_idempotent(tmp_path):
    _seed_lake(tmp_path)
    for _ in range(2):  # deuxième run = idempotence (mêmes fichiers, mêmes lignes)
        for asset in (
            "allrugby_staging_matches",
            "allrugby_staging_appearances",
            "allrugby_staging_profiles",
        ):
            result = _materialize(asset, tmp_path)
            assert result.returncode == 0, result.stderr[-2000:]
    matches = pl.read_parquet(
        tmp_path / "data" / "staging" / "match/source=allrugby/season=2023-2024" / "part.parquet"
    )
    apps = pl.read_parquet(
        tmp_path
        / "data"
        / "staging"
        / "appearance/source=allrugby/season=2023-2024"
        / "part.parquet"
    )
    profiles = pl.read_parquet(
        tmp_path
        / "data"
        / "staging"
        / "player_profile/source=allrugby/season=2023-2024"
        / "part.parquet"
    )
    SCHEMAS["match"].validate(matches)
    SCHEMAS["appearance"].validate(apps)
    SCHEMAS["player_profile"].validate(profiles)
    assert matches.height == 3 and apps.height == 3 * 46 and profiles.height == 2
    assert set(profiles["source_player_id"]) == {"5427", "5005"}
