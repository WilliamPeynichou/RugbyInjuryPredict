"""F22 : la revue marque infaisables les sensibilités que l'export ne peut pas porter."""

import polars as pl
import pytest

from rugby_risk.modeling.review import STRICT_CONFIDENCE, sensitivities

pytestmark = pytest.mark.unit


def _frame(conf_values: list[float]) -> pl.DataFrame:
    """Minimal frame with the columns `sensitivities()` inspects."""
    return pl.DataFrame(
        {
            "season_id": ["2022-2023"] * len(conf_values),
            "y_injury_conf": conf_values,
        }
    )


def test_strict_confidence_infeasible_below_export_max() -> None:
    """Export réel : confiance max 0,75 < 0,8 -> seuil strict listé infaisable, pas de crash."""
    sens = {s.label: s for s in sensitivities(_frame([0.6, 0.75, 0.75]), "m2_hierarchical")}
    strict = sens[f"Seuil de confiance {STRICT_CONFIDENCE}"]
    assert strict.infeasible is not None
    assert "0.75" in strict.infeasible
    assert strict.variant is None


def test_strict_confidence_feasible_when_export_reaches() -> None:
    sens = {s.label: s for s in sensitivities(_frame([0.6, 0.8]), "m2_hierarchical")}
    strict = sens[f"Seuil de confiance {STRICT_CONFIDENCE}"]
    assert strict.infeasible is None
    assert strict.variant is not None


def test_low_confidence_threshold_always_infeasible() -> None:
    """Le seuil 0,5 exigerait des épisodes < 0,6 que l'export ne matérialise jamais."""
    sens = sensitivities(_frame([0.8, 0.9]), "m2_hierarchical")
    low = next(s for s in sens if s.label == "Seuil de confiance 0,5")
    assert low.infeasible is not None
    assert low.variant is None


def test_covid_exclusion_infeasible_without_covid_seasons() -> None:
    sens = sensitivities(_frame([0.75]), "m2_hierarchical")
    covid = next(s for s in sens if s.label == "Exclusion des saisons COVID")
    assert covid.infeasible is not None
    assert covid.variant is None
