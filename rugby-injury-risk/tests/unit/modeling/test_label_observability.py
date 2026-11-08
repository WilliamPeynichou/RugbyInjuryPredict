"""Label observability: end-of-season rows without follow-up are censored, not negatives."""

from datetime import UTC, datetime, timedelta

import polars as pl

from rugby_risk.modeling.validation import LABEL_OBSERVABLE, with_label_observability


def _frame() -> pl.DataFrame:
    start = datetime(2024, 9, 1, tzinfo=UTC)
    rows = [
        {"player_key": p, "season_id": s, "kickoff_ts": start + timedelta(days=d), "y": y}
        for p, s, d, y in [
            ("a", "S1", 0, False),
            ("a", "S1", 7, False),
            ("a", "S1", 14, True),  # suivi 1 < 2 : non observable même si y = 1
            ("a", "S1", 21, False),
            ("a", "S2", 400, False),  # saison suivante : compteur repart de zéro
            ("b", "S1", 3, False),
        ]
    ]
    # Ordre d'entrée mélangé : la fonction trie elle-même par joueur puis date.
    return pl.DataFrame(rows).reverse()


def test_followup_counts_within_player_season() -> None:
    out = with_label_observability(_frame(), min_followup=2)
    flags = {
        (r["player_key"], r["season_id"], r["kickoff_ts"].day): r[LABEL_OBSERVABLE]
        for r in out.iter_rows(named=True)
    }
    a = [v for (p, s, _), v in sorted(flags.items()) if p == "a" and s == "S1"]
    assert sorted(a, reverse=True) == [True, True, False, False]
    assert not flags[("b", "S1", 4)]
    assert sum(v for (p, s, _), v in flags.items() if s == "S2") == 0


def test_does_not_read_the_target() -> None:
    df = _frame()
    flipped = df.with_columns(~pl.col("y"))
    a = with_label_observability(df, 1)[LABEL_OBSERVABLE]
    b = with_label_observability(flipped, 1)[LABEL_OBSERVABLE]
    assert a.to_list() == b.to_list()
