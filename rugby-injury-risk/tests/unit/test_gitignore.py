from pathlib import Path


def test_sensitive_patterns_are_ignored():
    text = Path(".gitignore").read_text()
    for pattern in ("data/raw/", "data/staging/", "data/review/", "*.duckdb", ".env", "mlruns/"):
        assert pattern in text.splitlines()
