"""F25 guard: forbidden columns raise, k-anonymity drops cells under 10 players."""

import polars as pl
import pytest

from rugby_risk.errors import PrivacyViolationError
from rugby_risk.serving.guard import (
    FORBIDDEN_PUBLIC_COLUMNS,
    MIN_SUPPORT,
    assert_public_safe,
    enforce_aggregation,
    make_public,
)

pytestmark = pytest.mark.unit


def _frame(n_players: int, extra: dict[str, list[object]] | None = None) -> pl.DataFrame:
    data: dict[str, list[object]] = {
        "position_code": ["PROP", "HOOKER"],
        "value": [0.1, 0.2],
        "n_players_support": [n_players, MIN_SUPPORT],
    }
    data.update(extra or {})
    return pl.DataFrame(data)


def test_forbidden_column_raises() -> None:
    for column in FORBIDDEN_PUBLIC_COLUMNS:
        frame = _frame(MIN_SUPPORT, {column: [1, 2]})
        with pytest.raises(PrivacyViolationError):
            assert_public_safe(frame, table="t")


def test_support_below_ten_is_dropped() -> None:
    out = enforce_aggregation(_frame(9))
    assert out["position_code"].to_list() == ["HOOKER"]


def test_support_at_ten_is_kept() -> None:
    out = make_public(_frame(10), table="t")
    assert out.height == 2


def test_min_support_cannot_go_below_ten() -> None:
    with pytest.raises(PrivacyViolationError):
        enforce_aggregation(_frame(5), min_support=5)


def test_support_column_mandatory() -> None:
    with pytest.raises(PrivacyViolationError):
        enforce_aggregation(pl.DataFrame({"a": [1]}))
