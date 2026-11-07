from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC = Path("src/rugby_risk/modeling")
FORBIDDEN = ("KFold", "train_test_split", "ShuffleSplit", "StratifiedKFold")


def test_no_random_split_anywhere_in_modeling():
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text and "test_no_random_kfold" not in path.name:
                offenders.append(f"{path}: {token}")
    assert not offenders, offenders


def test_rolling_origin_is_the_only_source_of_folds():
    runner = (SRC / "runner.py").read_text(encoding="utf-8")
    assert "season_folds(" in runner
    assert "model_selection" not in runner
