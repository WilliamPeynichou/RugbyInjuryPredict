"""Season rolling-origin splits (docs/06 §3.1). Random k-fold is forbidden here."""

from dataclasses import dataclass

import polars as pl

FINAL_TEST_SEASON = "2025-2026"


@dataclass(frozen=True)
class Fold:
    """One rolling-origin evaluation window."""

    fold_id: int
    train_seasons: tuple[str, ...]
    valid_season: str
    test_season: str

    def select(self, df: pl.DataFrame, seasons: tuple[str, ...] | None = None) -> pl.DataFrame:
        wanted = seasons if seasons is not None else ()
        return df.filter(pl.col("season_id").is_in(list(wanted)))


def season_folds(
    seasons: list[str],
    min_train_seasons: int = 5,
    test_final: str = FINAL_TEST_SEASON,
    covid_disrupted: set[str] | None = None,
    allow_final_test: bool = False,
) -> list[Fold]:
    """Rolling-origin folds: train < valid < test, consecutive seasons.

    `min_train_seasons` counts the estimation seasons excluding the validation season.

        A COVID-disrupted season is never used alone as a test season. `test_final` is excluded
        unless `allow_final_test=True` (it must be touched once per major version only).
    """
    covid = covid_disrupted or set()
    usable_test = [s for s in seasons if s not in covid]
    if test_final in usable_test and not allow_final_test:
        usable_test = [s for s in usable_test if s != test_final]
    folds: list[Fold] = []
    for test in usable_test:
        train_end = seasons.index(test)
        before = seasons[:train_end]
        if len(before) < min_train_seasons + 1:
            continue
        # train = estimation propre ; valid = saison précédant le test (hors train).
        train_rest = tuple(before[:-1])
        valid = before[-1]
        folds.append(
            Fold(fold_id=len(folds), train_seasons=train_rest, valid_season=valid, test_season=test)
        )
    return folds


LABEL_OBSERVABLE = "label_observable"


def with_label_observability(df: pl.DataFrame, min_followup: int) -> pl.DataFrame:
    """Flag rows whose label can be observed (docs/06 §3, censure de fin de saison).

    `y_injury` is reconstructed from absences (F13): an injury candidate needs at least
    `min_followup` later team matches in the same season. With fewer (end of season, playoff
    elimination, departure) `y_injury = 0` means "not observable", not "no injury". The
    follow-up count uses every squad row of the player (on_sheet or not), never the target,
    so the exclusion does not condition on the outcome.
    """
    later = pl.len().over("player_key", "season_id") - pl.int_range(pl.len()).over(
        "player_key", "season_id"
    )
    return df.sort("player_key", "kickoff_ts").with_columns(
        ((later - 1) >= min_followup).alias(LABEL_OBSERVABLE)
    )
