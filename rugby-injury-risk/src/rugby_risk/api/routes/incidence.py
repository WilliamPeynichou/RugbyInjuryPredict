"""Routes d'incidence observée et de calibration du modèle (F26)."""

from __future__ import annotations

import polars as pl
from fastapi import APIRouter, HTTPException

from rugby_risk.api.deps import RepositoryDep, clean_rows
from rugby_risk.api.schemas import CalibrationRow, IncidenceRow

router = APIRouter(tags=["incidence"])


@router.get("/incidence", response_model=list[IncidenceRow])
def incidence(
    repository: RepositoryDep,
    season: str | None = None,
) -> list[IncidenceRow]:
    frame = repository.table("pred_position_season")
    if season is not None:
        frame = frame.filter(pl.col("season_id") == season)
        if frame.is_empty():
            raise HTTPException(status_code=404, detail=f"Saison introuvable : {season}")
    return [IncidenceRow(**row) for row in clean_rows(frame)]


@router.get("/calibration", response_model=list[CalibrationRow])
def calibration(
    repository: RepositoryDep,
    model_version: str | None = None,
) -> list[CalibrationRow]:
    frame = repository.table("calibration_public")
    if model_version is not None:
        frame = frame.filter(pl.col("model_version") == model_version)
    if frame.is_empty():
        raise HTTPException(status_code=404, detail="Calibration introuvable")
    return [CalibrationRow(**row) for row in clean_rows(frame)]
