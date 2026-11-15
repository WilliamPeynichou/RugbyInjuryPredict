from datetime import date

import polars as pl
import pytest

from rugby_risk.entity_resolution.anchor import anchor_pairs

pytestmark = pytest.mark.unit


def _apps(rows):
    return pl.DataFrame(
        rows,
        schema={
            "key": pl.String,
            "source": pl.String,
            "match_key": pl.String,
            "match_date": pl.Date,
            "team": pl.String,
            "shirt_number": pl.Int64,
        },
    )


def test_anchor_on_shared_match_same_club_same_shirt():
    apps = _apps(
        [
            (
                "lnr:1",
                "lnr",
                "ASM Clermont Auvergne|Toulouse|2024-02-02",
                date(2024, 2, 2),
                "ASM Clermont Auvergne",
                9,
            ),
            (
                "allrugby:1",
                "allrugby",
                "ASM Clermont Auvergne|Toulouse|2024-02-02",
                date(2024, 2, 2),
                "ASM Clermont",
                9,
            ),
            (
                "allrugby:2",
                "allrugby",
                "ASM Clermont Auvergne|Toulouse|2024-02-02",
                date(2024, 2, 2),
                "ASM Clermont",
                10,
            ),
        ]
    )
    pairs = anchor_pairs(apps)
    assert pairs.rows(named=True) == [{"key_l": "lnr:1", "key_r": "allrugby:1", "anchor": True}]


def test_anchor_needs_same_shirt_and_match():
    apps = _apps(
        [
            (
                "lnr:1",
                "lnr",
                "Toulouse|Clermont|2024-02-02",
                date(2024, 2, 2),
                "Stade Toulousain",
                9,
            ),
            (
                "allrugby:1",
                "allrugby",
                "Toulouse|Clermont|2024-02-02",
                date(2024, 2, 2),
                "Toulouse",
                10,
            ),
            (
                "allrugby:2",
                "allrugby",
                "Toulouse|Racing|2024-02-09",
                date(2024, 2, 9),
                "Toulouse",
                9,
            ),
        ]
    )
    assert anchor_pairs(apps).is_empty()
