"""h(N) curves by position (F20, docs/06 §2): risk of the next match after N consecutive ones.

Profiles (per-position medians) are computed on the training rows of the model only. A curve
is `model.predict_proba` evaluated on a synthetic frame where `consecutive_matches` = N and
every other feature is frozen at the scenario profile: an association, not a causal effect.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import polars as pl
import yaml

SCENARIOS_PATH = Path("configs/scenarios.yaml")
CURVE_VARIABLE = "consecutive_matches"


@dataclass(frozen=True)
class Scenarios:
    minutes_played: float
    n_range: tuple[int, ...]
    overrides: dict[str, dict[str, Any]]


def load_scenarios(path: Path = SCENARIOS_PATH) -> Scenarios:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    overrides = {name: dict(values or {}) for name, values in raw["scenarios"].items()}
    if "median" not in overrides:
        raise ValueError(f"{path} : le scénario 'median' est obligatoire")
    return Scenarios(
        minutes_played=float(raw["minutes_played"]),
        n_range=tuple(range(int(raw["n_min"]), int(raw["n_max"]) + 1)),
        overrides=overrides,
    )


def scenario_profiles(
    train: pl.DataFrame, numeric: Sequence[str], categorical: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Per `position_code`: median of numeric features, most frequent category otherwise."""
    profiles: dict[str, dict[str, Any]] = {}
    for (code,), rows in train.group_by(["position_code"], maintain_order=True):
        profile: dict[str, Any] = {}
        for col in numeric:
            values = rows[col].cast(pl.Float64).drop_nulls()
            profile[col] = float(values.median()) if len(values) else None  # type: ignore[arg-type]
        for col in categorical:
            mode = rows[col].cast(pl.String).drop_nulls().mode().sort()
            profile[col] = mode[0] if len(mode) else None
        profiles[str(code)] = profile
    return profiles


class CurveModel(Protocol):
    profiles_: dict[str, dict[str, Any]]
    scenarios_: Scenarios

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray: ...


def scenario_frame(
    profile: dict[str, Any],
    overrides: dict[str, Any],
    n_range: Iterable[int],
    minutes: float,
    position_code: str,
) -> pl.DataFrame:
    ns = list(n_range)
    base = {**profile, **overrides}
    data: dict[str, list[Any]] = {k: [v] * len(ns) for k, v in base.items()}
    data[CURVE_VARIABLE] = [float(n) for n in ns]
    data["minutes_played"] = [minutes] * len(ns)
    data["position_code"] = [position_code] * len(ns)
    return pl.DataFrame(data, strict=False)


def hazard_curve(
    model: CurveModel,
    position_code: str,
    n_range: Iterable[int] | None = None,
    scenario: str = "median",
) -> np.ndarray:
    """h(N) for N in `n_range` for a position, under a named scenario."""
    if position_code not in model.profiles_:
        raise KeyError(f"Poste absent du train : {position_code}")
    scenarios = model.scenarios_
    if scenario not in scenarios.overrides:
        raise KeyError(f"Scénario inconnu : {scenario} (connus : {sorted(scenarios.overrides)})")
    frame = scenario_frame(
        model.profiles_[position_code],
        scenarios.overrides[scenario],
        n_range if n_range is not None else scenarios.n_range,
        scenarios.minutes_played,
        position_code,
    )
    return np.asarray(model.predict_proba(frame), dtype=float)


def cumulative_risk(hazards: Sequence[float] | np.ndarray) -> float:
    """P(at least one injury over K matches) = 1 - prod(1 - h_k) (independent matches)."""
    h = np.asarray(hazards, dtype=float)
    if ((h < 0) | (h > 1)).any():
        raise ValueError("Les hazards doivent être des probabilités dans [0, 1]")
    return float(1.0 - np.prod(1.0 - h))
