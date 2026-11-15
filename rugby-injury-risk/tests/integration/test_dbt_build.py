import json
import subprocess
import sys

import pytest
from dbt.cli.main import dbtRunner

from rugby_risk.injuries.rules import dbt_vars

pytestmark = pytest.mark.integration


def test_dbt_build_on_empty_staging(tmp_path, monkeypatch):
    monkeypatch.setenv("WAREHOUSE_PATH", str(tmp_path / "w.duckdb"))
    monkeypatch.setenv("ENV", "test")
    subprocess.run([sys.executable, "scripts/export_seeds.py"], check=True)
    result = dbtRunner().invoke(
        [
            "build",
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--log-path",
            str(tmp_path / "logs"),
            "--target-path",
            str(tmp_path / "target"),
            "--vars",
            json.dumps({"staging_dir": str(tmp_path / "empty"), **dbt_vars()}),
        ]
    )
    assert result.success
