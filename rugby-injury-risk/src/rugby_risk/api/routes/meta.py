"""Routes de méta-données : postes, scénarios, registre des modèles (F26)."""

from __future__ import annotations

from typing import Final

from fastapi import APIRouter

from rugby_risk.api.deps import RepositoryDep, clean_rows
from rugby_risk.api.schemas import ModelRow, Position, Scenario
from rugby_risk.reference import positions

router = APIRouter(tags=["meta"])

SCENARIOS: Final[tuple[Scenario, ...]] = (
    Scenario(
        scenario="median",
        description="Profil médian du poste (ceteris paribus : seul l'enchaînement varie).",
    ),
    Scenario(
        scenario="international_november",
        description="Fenêtre internationale de novembre (match supplémentaire en semaine).",
    ),
    Scenario(
        scenario="return_from_injury",
        description="Retour de blessure dans les 8 dernières semaines, 1 blessure dans l'année.",
    ),
    Scenario(
        scenario="short_turnaround_block",
        description="Bloc dense : 6 jours de repos entre deux matchs, rotation réduite.",
    ),
)


@router.get("/models", response_model=list[ModelRow])
def list_models(repository: RepositoryDep) -> list[ModelRow]:
    return [ModelRow(**row) for row in clean_rows(repository.table("model_registry_public"))]


@router.get("/positions", response_model=list[Position])
def list_positions() -> list[Position]:
    return [Position(**row) for row in positions().iter_rows(named=True)]


@router.get("/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS)
