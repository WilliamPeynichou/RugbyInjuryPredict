"""Null model: predicts the training base rate.

Not a contender: M0 (référence à battre) lives in `baselines.py` (F19). ConstantModel
reste comme sonde déterministe du protocole F18.
"""

from collections.abc import Callable
from typing import Any

import numpy as np
import polars as pl

from rugby_risk.modeling.base import RiskModel


class ConstantModel:
    """P(injury) = prevalence of the target on the training folds."""

    name = "constant"

    def __init__(self, target_col: str = "y_injury") -> None:
        self.target_col = target_col
        self.rate_: float | None = None

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "ConstantModel":
        del valid
        col = train.get_column(self.target_col).to_numpy()
        if col.size == 0:
            raise ValueError(f"Colonne cible vide: {self.target_col}")
        self.rate_ = float(np.mean(col))
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self.rate_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        return np.full(len(df), self.rate_, dtype=float)

    def params(self) -> dict[str, Any]:
        return {"target_col": self.target_col, "base_rate": self.rate_}


def registry() -> dict[str, Callable[[], RiskModel]]:
    """Model factories by name (CLI `rugby-risk train <model>`)."""
    from rugby_risk.modeling.baselines import (  # noqa: PLC0415 - évite cycle d'imports
        GlobalRateModel,
        PositionRateModel,
    )

    return {
        ConstantModel.name: lambda: ConstantModel(),  # noqa: PLW0108 - factory standard
        GlobalRateModel.name: lambda: GlobalRateModel(),  # noqa: PLW0108
        PositionRateModel.name: lambda: PositionRateModel(),  # noqa: PLW0108
    }
