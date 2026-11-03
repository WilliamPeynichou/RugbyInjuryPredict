import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_sensitive_files.py"


@pytest.mark.parametrize(
    "filename",
    [
        "data/raw/page.html",
        "rugby-injury-risk/data/staging/page.parquet",
        "data/warehouse.duckdb",
        ".env",
        "mlruns/experiment.json",
    ],
)
def test_hook_rejects_sensitive_files(filename):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), filename], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1
    assert filename in result.stderr


@pytest.mark.parametrize("filename", [".env.example", "data/reference/positions.csv", "src/app.py"])
def test_hook_accepts_source_files(filename):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), filename], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
