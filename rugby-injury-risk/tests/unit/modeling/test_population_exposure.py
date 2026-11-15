"""S18 : périmètre titulaires et exposition par titularisation (minutes hors des modèles)."""

import polars as pl
import pytest

from rugby_risk.modeling.runner import (
    EXPOSURE_REFERENCE_MINUTES,
    OBSERVED_MINUTES,
    ExperimentConfig,
    estimation_rows,
)
from tests.hazard_factory import hazard_frame

pytestmark = pytest.mark.unit

SEASONS = ("2020-2021",)


@pytest.fixture(scope="module")
def frame() -> pl.DataFrame:
    df = hazard_frame(players=60, seasons=1, matches=8, seed=3)
    starter = (pl.int_range(pl.len()) % 3 != 0).alias("is_starter")
    return df.with_columns(starter)


def test_default_keeps_all_rows_and_observed_minutes(frame: pl.DataFrame) -> None:
    rows = estimation_rows(frame, SEASONS, ExperimentConfig(min_label_followup=0))
    assert OBSERVED_MINUTES not in rows.columns
    assert rows["minutes_played"].n_unique() > 1
    assert not rows["is_starter"].all()


def test_starters_population_drops_substitutes(frame: pl.DataFrame) -> None:
    config = ExperimentConfig(min_label_followup=0, population="starters")
    rows = estimation_rows(frame, SEASONS, config)
    assert rows.height > 0
    assert rows["is_starter"].all()


def test_per_start_exposure_hides_match_minutes_from_models(frame: pl.DataFrame) -> None:
    config = ExperimentConfig(min_label_followup=0, exposure="per_start")
    rows = estimation_rows(frame, SEASONS, config)
    # Les modèles lisent `minutes_played` : constante, donc aucune information du match.
    assert rows["minutes_played"].unique().to_list() == [EXPOSURE_REFERENCE_MINUTES]
    assert rows[OBSERVED_MINUTES].n_unique() > 1


@pytest.mark.parametrize("field", ["population", "exposure"])
def test_unknown_option_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match="inconnue"):
        ExperimentConfig(**{field: "nope"})
