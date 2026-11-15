from pathlib import Path

import polars as pl
import pytest

from rugby_risk.cli import main
from rugby_risk.entity_resolution import review
from rugby_risk.entity_resolution.review import decide, read_review_queue, write_review_queue

pytestmark = pytest.mark.unit


def test_review_queue_roundtrip(tmp_path):
    queue = pl.DataFrame({"key_l": ["a:1"], "key_r": ["b:2"], "match_probability": [0.8]})
    path = write_review_queue(queue, tmp_path / "er_queue.csv")
    loaded = read_review_queue(path)
    assert loaded.row(0, named=True)["key_l"] == "a:1"
    assert read_review_queue(tmp_path / "missing.csv").is_empty()


def test_decide_updates_overrides(tmp_path):
    overrides = tmp_path / "er_overrides.csv"
    overrides.write_text("source,source_player_id,player_id\n")
    decide("espn:9", "42", overrides)
    decide("lnr:1", "NEW", overrides)
    decide("espn:9", "REJECT", overrides)  # remplace la décision précédente
    frame = pl.read_csv(overrides, infer_schema=False)
    lnr = frame.filter(frame["source"] == "lnr").row(0, named=True)
    assert lnr["player_id"] == "NEW"
    assert frame["source"].to_list() == ["lnr", "espn"]  # décision REJECT persistée, pas doublon


def test_cli_review_and_decide(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_review_queue(
        pl.DataFrame({"key_l": ["a:1"], "key_r": ["b:2"], "match_probability": [None]}),
        Path("data/review/er_queue.csv"),
    )
    assert main(["er", "review"]) == 0
    out = capsys.readouterr().out
    assert "a:1 <-> b:2" in out
    (tmp_path / "data/reference").mkdir(parents=True)
    overrides = tmp_path / "data/reference/er_overrides.csv"
    overrides.write_text("source,source_player_id,player_id\n")
    monkeypatch.setattr(review, "REFERENCE_DIR", tmp_path / "data/reference")
    assert main(["er", "decide", "espn:9", "7"]) == 0
    assert "espn" in overrides.read_text()
