"""Common model interface (F18). All models (F19+) implement this protocol."""

from typing import Any, Protocol, runtime_checkable

import numpy as np
import polars as pl


@runtime_checkable
class RiskModel(Protocol):
    """Binary risk model over played rows of `ml_player_match`."""

    name: str

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "RiskModel":
        """Fit on training folds. `valid` is the next season (early stopping, calibration)."""
        ...

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        """P(injury) per row. Callers pass played rows only (selection is modelled in F21)."""
        ...

    def params(self) -> dict[str, Any]:
        """Hyperparameters and feature list, logged to MLflow."""
        ...
