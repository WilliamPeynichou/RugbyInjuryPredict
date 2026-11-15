import pytest

from rugby_risk.injuries.evaluate import compute_metrics, isotonic_recalibration

pytestmark = pytest.mark.unit


def _rows():
    return [
        {"episode_kind": "episode", "source_confidence": 0.95, "decision": "injury"},
        {"episode_kind": "episode", "source_confidence": 0.8, "decision": "injury"},
        {"episode_kind": "episode", "source_confidence": 0.5, "decision": "not_injury"},
        {"episode_kind": "non_episode", "source_confidence": 0.0, "decision": "not_injury"},
        {"episode_kind": "non_episode", "source_confidence": 0.0, "decision": "not_injury"},
        {"episode_kind": "non_episode", "source_confidence": 0.0, "decision": "injury"},
        {"episode_kind": "episode", "source_confidence": 0.7, "decision": "unsure"},  # ignoré
    ]


def test_precision_recall():
    m = compute_metrics(_rows())
    assert m.precision == pytest.approx(0.6667)
    assert m.recall == pytest.approx(0.6667)
    assert m.n_labeled == 6


def test_precision_by_band():
    m = compute_metrics(_rows())
    bands = {b: p for b, n, p in m.precision_by_band}
    assert bands["[0.9, 1.0)"] == 1.0
    assert bands["[0.6, 0.9)"] == 1.0
    assert bands["[0.0, 0.6)"] == 0.0


def test_isotonic_monotone():
    pairs = [(0.5, 0), (0.6, 0), (0.7, 1), (0.8, 1), (0.9, 0)]
    cal = isotonic_recalibration(pairs)
    values = [v for _, v in cal]
    assert values == sorted(values)  # non-décroissant
    assert len(cal) == len(pairs)
