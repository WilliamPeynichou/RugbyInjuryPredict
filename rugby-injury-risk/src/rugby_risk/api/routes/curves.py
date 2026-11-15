"""Routes de courbes h(N) et de risque cumulé (F26)."""

from __future__ import annotations

from typing import Final, cast

import polars as pl
from fastapi import APIRouter, HTTPException, Query

from rugby_risk.api.deps import Repository, RepositoryDep
from rugby_risk.api.schemas import (
    MAX_K_MATCHES,
    POSITION_CODES,
    WARNING,
    Cumulative,
    Curve,
    CurvePoint,
    PositionCode,
    ScenarioName,
)

router = APIRouter(tags=["courbes"])
COMPARE_MIN: Final = 2
COMPARE_MAX: Final = 4
CURVE_TABLE: Final = "pred_position_curve"


def _curve_frame(
    repository: Repository, position: str, scenario: str, model_version: str | None
) -> pl.DataFrame:
    frame = repository.table(CURVE_TABLE).filter(
        (pl.col("position_code") == position) & (pl.col("scenario") == scenario)
    )
    if model_version is not None:
        frame = frame.filter(pl.col("model_version") == model_version)
    if frame.is_empty():
        raise HTTPException(
            status_code=404,
            detail=f"Courbe introuvable : {position} / {scenario}"
            + ("" if model_version is None else f" / {model_version}"),
        )
    latest_version = str(frame["model_version"].max())
    return frame.filter(pl.col("model_version") == latest_version).sort("n_consecutive")


def _curve(
    repository: Repository, position: str, scenario: str, model_version: str | None
) -> Curve:
    frame = _curve_frame(repository, position, scenario, model_version)
    first = frame.row(0, named=True)
    return Curve(
        model_version=str(first["model_version"]),
        position_code=position,
        scenario=cast(ScenarioName, scenario),
        n_players_support=int(first["n_players_support"]),
        points=[
            CurvePoint(
                n_consecutive=int(r["n_consecutive"]),
                p_mean=float(r["p_mean"]),
                p_low90=float(r["p_low90"]),
                p_high90=float(r["p_high90"]),
                cum_mean=float(r["cum_mean"]),
                cum_low90=float(r["cum_low90"]),
                cum_high90=float(r["cum_high90"]),
            )
            for r in frame.iter_rows(named=True)
        ],
        warning=WARNING,
    )


@router.get("/curves", response_model=Curve)
def get_curve(
    repository: RepositoryDep,
    position: PositionCode,
    scenario: ScenarioName = "median",
    model_version: str | None = None,
) -> Curve:
    return _curve(repository, position, scenario, model_version)


@router.get("/curves/compare", response_model=list[Curve])
def compare_curves(
    repository: RepositoryDep,
    positions: str = Query(..., description="codes séparés par des virgules, 2 à 4"),
    scenario: ScenarioName = "median",
) -> list[Curve]:
    codes = [c.strip().upper() for c in positions.split(",") if c.strip()]
    if not COMPARE_MIN <= len(codes) <= COMPARE_MAX:
        raise HTTPException(status_code=422, detail="2 à 4 postes requis pour comparer")
    unknown = [c for c in codes if c not in POSITION_CODES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Postes inconnus : {unknown}")
    return [_curve(repository, code, scenario, None) for code in codes]


@router.get("/cumulative", response_model=Cumulative)
def cumulative(
    repository: RepositoryDep,
    position: PositionCode,
    k: int = Query(..., ge=1, le=MAX_K_MATCHES),
    scenario: ScenarioName = "median",
) -> Cumulative:
    """Risque cumulé sur k matchs consécutifs : lit cum_* au point n_consecutive = k - 1."""
    frame = _curve_frame(repository, position, scenario, None)
    row = frame.filter(pl.col("n_consecutive") == k - 1)
    if row.is_empty():
        raise HTTPException(status_code=422, detail=f"k={k} hors de l'horizon exporté")
    point = row.row(0, named=True)
    return Cumulative(
        model_version=str(point["model_version"]),
        position_code=position,
        scenario=scenario,
        k_matches=k,
        risk_mean=float(point["cum_mean"]),
        risk_low90=float(point["cum_low90"]),
        risk_high90=float(point["cum_high90"]),
        warning=WARNING,
    )
