from datetime import date

import pytest

from rugby_risk.injuries.fusion import (
    Episode,
    Signal,
    _mergeable,
    _severity,
    fuse,
    score_episode,
)
from rugby_risk.injuries.rules import load_rules

pytestmark = pytest.mark.unit
RULES = load_rules().fusion
D = date  # raccourci


def _exit(pid: int, day: int, strength: float = 0.8, match_id: int = 10) -> Signal:
    return Signal(
        kind="exit",
        player_id=pid,
        signal_date=D(2024, 1, day),
        strength=strength,
        match_id=match_id,
        context="match",
    )


def _absence(pid: int, start: int, end: int, ret: int | None = None) -> Signal:
    return Signal(
        kind="absence",
        player_id=pid,
        signal_date=D(2024, 1, start),
        run_end=D(2024, 1, end),
        return_date=D(2024, 1, ret) if ret else None,
    )


def _announce(pid: int, day: int, region: str | None = None, duration: int | None = None) -> Signal:
    return Signal(
        kind="announcement",
        player_id=pid,
        signal_date=D(2024, 1, day),
        body_region=region,
        detailed=region is not None or duration is not None,
    )


def test_score_combinations():
    assert score_episode([_announce(1, 5)], RULES) == 0.7
    assert score_episode([_announce(1, 5, region="knee")], RULES) == 0.8
    assert score_episode([_exit(1, 5, strength=0.8)], RULES) == round(0.8 * 0.6, 4)
    assert score_episode([_absence(1, 5, 9, ret=12)], RULES) == 0.4
    assert score_episode([_exit(1, 5), _absence(1, 6, 9, ret=12)], RULES) == 0.75
    assert score_episode([_exit(1, 5), _announce(1, 5)], RULES) == 0.9
    combo = [_exit(1, 5), _absence(1, 6, 9, ret=12), _announce(1, 5)]
    assert score_episode(combo, RULES) == 0.95
    assert score_episode(combo, RULES) <= 0.99


def test_episode_attributes():
    (ep,) = fuse([_exit(1, 10), _absence(1, 12, 17, ret=24)], RULES)
    assert ep.onset_date == D(2024, 1, 10) and ep.onset_match_id == 10
    assert ep.context == "match"
    assert ep.return_date == D(2024, 1, 24)
    assert ep.days_missed == 14 and ep.severity_class == "moderate"
    assert not ep.censored
    assert ep.source_confidence == 0.75
    assert ep.signals == ["absence", "exit"]


def test_censored_end_of_season():
    (ep,) = fuse([_absence(1, 20, 27, ret=None)], RULES)
    assert ep.onset_date == D(2024, 1, 20)
    assert ep.censored and ep.return_date is None and ep.days_missed is None
    assert ep.severity_class == "unknown"


def test_grouping_window_10_days():
    # deux signaux à 8 jours = un seul épisode ; à 12 jours = deux épisodes
    one = fuse([_exit(1, 1), _announce(1, 9)], RULES)
    two = fuse([_exit(1, 1), _announce(1, 13)], RULES)
    assert len(one) == 1 and len(two) == 2


def test_merge_close_episodes_same_region():
    a = Episode(
        1,
        D(2024, 1, 1),
        10,
        "match",
        "knee",
        None,
        False,
        D(2024, 1, 10),
        9,
        "minimal_mild",
        False,
        0.4,
        ["absence"],
        [],
    )
    b = Episode(
        1,
        D(2024, 1, 15),
        20,
        "match",
        "knee",
        None,
        False,
        D(2024, 1, 30),
        15,
        "moderate",
        False,
        0.7,
        ["announcement"],
        [],
    )
    merged = fuse([], RULES)  # no-op sanity
    assert merged == []
    assert _mergeable(a, b, RULES)
    episodes = fuse(
        [
            Signal("absence", 1, D(2024, 1, 1), return_date=D(2024, 1, 10)),
            Signal("announcement", 1, D(2024, 1, 15), body_region="knee"),
        ],
        RULES,
    )
    assert len(episodes) == 1
    assert episodes[0].body_region == "knee"
    assert episodes[0].signals == ["absence", "announcement"]


def test_no_merge_different_region():
    a = Episode(
        1,
        D(2024, 1, 1),
        10,
        "match",
        "knee",
        None,
        False,
        D(2024, 1, 5),
        4,
        "minimal_mild",
        False,
        0.4,
        ["absence"],
        [],
    )
    b = Episode(
        1,
        D(2024, 1, 6),
        20,
        "match",
        "shoulder",
        None,
        False,
        D(2024, 1, 20),
        14,
        "moderate",
        False,
        0.7,
        ["announcement"],
        [],
    )
    assert not _mergeable(a, b, RULES)


def test_opt_out_excluded():
    episodes = fuse([_exit(9, 5), _exit(1, 5)], RULES, opt_out={9})
    assert [e.player_id for e in episodes] == [1]


def test_severity_bounds():
    assert _severity(None) == "unknown"
    assert _severity(0) == "minimal_mild" and _severity(7) == "minimal_mild"
    assert _severity(8) == "moderate" and _severity(28) == "moderate"
    assert _severity(29) == "severe"
