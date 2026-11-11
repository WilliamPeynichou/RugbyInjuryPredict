"""Pydantic schemas for the public API (F26). All payloads are aggregate-only."""

from __future__ import annotations

from typing import Annotated, Final, Literal, get_args

from pydantic import AfterValidator, BaseModel, Field

from rugby_risk.reference import positions

# Vocabulaire contrôlé : source unique = data/reference/positions.csv (aucun code en dur).
POSITION_CODES: Final = frozenset(positions()["position_code"].to_list())


def _check_position(value: str) -> str:
    if value not in POSITION_CODES:
        raise ValueError(f"Poste inconnu : {value}")
    return value


PositionCode = Annotated[str, AfterValidator(_check_position)]
ScenarioName = Literal[
    "median", "international_november", "return_from_injury", "short_turnaround_block"
]
MAX_N_CONSECUTIVE: Final = 15
MAX_K_MATCHES: Final = MAX_N_CONSECUTIVE + 1
SCENARIO_NAMES: Final = frozenset(get_args(ScenarioName))
WARNING: Final = (
    "Association statistique, non causale. Cible : blessures avec arrêt d'au moins 2 matchs "
    "(sous-déclarées). Ordre de grandeur par poste, pas un pronostic individuel."
)


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class Position(BaseModel):
    position_code: PositionCode
    position_label_fr: str
    position_group: str
    unit: str


class Scenario(BaseModel):
    scenario: ScenarioName
    description: str


class CurvePoint(BaseModel):
    n_consecutive: int = Field(ge=0, le=MAX_N_CONSECUTIVE)
    p_mean: float
    p_low90: float
    p_high90: float
    cum_mean: float
    cum_low90: float
    cum_high90: float


class Curve(BaseModel):
    model_version: str
    position_code: PositionCode
    scenario: ScenarioName
    n_players_support: int
    points: list[CurvePoint]
    warning: str


class Cumulative(BaseModel):
    model_version: str
    position_code: PositionCode
    scenario: ScenarioName
    k_matches: int = Field(ge=1, le=MAX_K_MATCHES)
    risk_mean: float
    risk_low90: float
    risk_high90: float
    warning: str


class IncidenceRow(BaseModel):
    season_id: str
    position_code: PositionCode
    position_group: str
    incidence_per_1000h: float | None
    incidence_low90: float | None
    incidence_high90: float | None
    injuries_count_bucket: str
    exposure_hours: float
    n_players_support: int


class CalibrationRow(BaseModel):
    model_version: str
    test_season: str
    position_group: str
    bin: int
    p_pred_mean: float
    p_obs: float
    n: int


class ModelRow(BaseModel):
    model_version: str
    model_name: str
    role: str
    promoted: bool
    train_seasons: str
    test_season: str
    dataset_version: str
    brier: float | None
    brier_low90: float | None
    brier_high90: float | None
    brier_skill: float | None
    logloss: float | None
    auc_roc: float | None
    calib_slope: float | None
    notes: str | None
