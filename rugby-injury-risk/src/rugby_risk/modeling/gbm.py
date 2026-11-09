"""M3 gradient-boosting challenger (F23, docs/06 §2): calibrated histogram GBM, SHAP, ALE.

Role: check whether a non-parametric model finds interactions missed by M1/M2 — not a public
model unless a documented human decision says so. Exposure enters as the feature
`log_exposure = log(minutes_played/80)` (documented choice: a single channel keeps SHAP and
the isotone calibration consistent; `init_score` would bypass calibration), under a forced
non-decreasing monotone constraint: the tree analogue of the offset of docs/06 §2. Without it
the trees learn reverse causation (an injured player is replaced early, and the label itself
uses early exits, F12) — real run of 2026-11-09: ROC AUC 0.90, exposure first in SHAP, h(N)
at 80 minutes collapsed to 0. Hyperparameters
are selected on the validation season only (reduced grid, log-loss); the isotonic calibration
is fit on validation predictions of the final model and applied to the test season. Trees
handle missing values natively (sentinel 999 stays a split, never imputed).

Implémentation : `sklearn.ensemble.HistGradientBoostingClassifier` (gradient boosting par
histogrammes, même famille que LightGBM). LightGBM exige `libomp`, une dépendance système
absente de la machine de développement ; sklearn est déjà une dépendance du projet, donc
`uv sync` suffit (journal F23).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, cast

import numpy as np
import pandas as pd
import polars as pl

from rugby_risk.features.registry import FEATURES
from rugby_risk.modeling.ale import ale_1d
from rugby_risk.modeling.curves import (
    SCENARIOS_PATH,
    Scenarios,
    hazard_curve,
    load_scenarios,
    scenario_profiles,
)

EXPOSURE_FEATURE: Final = "log_exposure"
# Offset arbre (docs/06 §2) : risque non décroissant avec l'exposition, jamais désactivable.
EXPOSURE_MONOTONE: Final = 1
CATEGORICAL_FEATURES: Final = ("position_code",)
# Grille réduite (docs/06 §2, ≤ 30 essais) : réglée sur la saison de validation uniquement.
_PARAM_GRID: Final = tuple(
    {"learning_rate": lr, "max_leaf_nodes": leaves, "min_samples_leaf": child, "max_iter": it}
    for lr in (0.05, 0.15)
    for leaves in (15, 31)
    for child in (50, 200)
    for it in (300,)
)
_SHAP_MAX_ROWS: Final = 5000


def _feature_columns(df: pl.DataFrame) -> list[str]:
    return [c for c in FEATURES if c in df.columns]


def _shap_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    """SHAP exige une matrice numérique : catégorielles -> codes (NaN si niveau inconnu)."""
    out = frame.copy()
    for col in CATEGORICAL_FEATURES:
        out[col] = out[col].cat.codes.astype(float)
        out.loc[out[col] < 0, col] = float("nan")
    return out


class GBMRiskModel:
    """Histogram gradient boosting + isotone calibration (validation). `RiskModel`."""

    name = "m3_gbm"
    registry_name = "rugby-risk-m3"
    requires_eligible = False

    def __init__(
        self,
        *,
        seed: int = 0,
        monotone: dict[str, int] | None = None,
        scenarios_path: Path = SCENARIOS_PATH,
    ) -> None:
        if monotone and monotone.get(EXPOSURE_FEATURE, EXPOSURE_MONOTONE) != EXPOSURE_MONOTONE:
            raise ValueError(f"{EXPOSURE_FEATURE} : contrainte croissante imposée (offset)")
        self.seed = seed
        self.monotone = monotone or {}
        self.scenarios_: Scenarios = load_scenarios(scenarios_path)
        self.features_: list[str] = []
        self.best_params_: dict[str, Any] = {}
        self.best_loss_: float = np.inf
        self.iso_: Any = None
        self.profiles_: dict[str, dict[str, Any]] = {}
        self.clf_: Any = None
        self._train_categories: dict[str, list[str]] = {}
        self._valid_X: pd.DataFrame | None = None
        self._valid_group: np.ndarray | None = None

    # --- features -------------------------------------------------------------------------

    def _frame(self, df: pl.DataFrame) -> pd.DataFrame:
        columns = list(dict.fromkeys([*self.features_, *CATEGORICAL_FEATURES]))
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"Colonnes absentes : {missing}")
        frame = df.select(columns).to_pandas()
        frame[self.features_] = frame[self.features_].astype(float)
        frame[EXPOSURE_FEATURE] = np.log(
            df.get_column("minutes_played").cast(pl.Float64).to_numpy() / 80.0
        )
        for col in CATEGORICAL_FEATURES:  # prédiction : niveaux du train, inconnus -> NaN
            known = self._train_categories.get(col)
            frame[col] = pd.Categorical(frame[col].astype(str), categories=known if known else None)
        return frame

    def _target(self, df: pl.DataFrame) -> np.ndarray:
        return df.get_column("y_injury").cast(pl.Float64).to_numpy()

    # --- ajustement -------------------------------------------------------------------------

    def fit(
        self, train: pl.DataFrame, valid: pl.DataFrame | None = None, eligible: Any = None
    ) -> GBMRiskModel:
        del eligible  # M3 ne corrige pas la sélection (F21) : challenger exploratoire
        from sklearn.ensemble import (  # noqa: PLC0415
            HistGradientBoostingClassifier,
        )
        from sklearn.isotonic import IsotonicRegression  # noqa: PLC0415
        from sklearn.metrics import log_loss  # noqa: PLC0415

        if valid is None or len(valid) == 0:
            raise ValueError("M3 exige la saison de validation (calibration isotone, docs/06)")
        schema = train.schema
        self.features_ = [
            c
            for c in _feature_columns(train)
            # position_code en catégorielle native ; codes/labels textuels écartés
            if c not in ("position_code", "position_group", "unit", "competition_code", "surface")
            # colonnes 100 % nulles au train : rien à apprendre (cf. design.py, termes dégénérés)
            and train[c].null_count() < len(train)
            # arbres : numériques et booléens uniquement (NaN natifs)
            and (schema[c].is_numeric() or schema[c] == pl.Boolean)
        ]
        x_train = self._frame(train)
        x_valid = self._frame(valid)
        y_train, y_valid = self._target(train), self._target(valid)
        for col in CATEGORICAL_FEATURES:
            cats = sorted(set(x_train[col].astype(str)))
            self._train_categories[col] = cats
            x_train[col] = pd.Categorical(x_train[col].astype(str), categories=cats)
            x_valid[col] = pd.Categorical(x_valid[col].astype(str), categories=cats)

        # Mêmes contraintes pour la grille et le modèle final (sinon réglage incohérent).
        cst = {**self.monotone, EXPOSURE_FEATURE: EXPOSURE_MONOTONE}
        constraints = [cst.get(c, 0) for c in x_train.columns]
        best_params = dict(_PARAM_GRID[0])
        for params in _PARAM_GRID:
            candidate = HistGradientBoostingClassifier(
                random_state=self.seed,
                categorical_features=list(CATEGORICAL_FEATURES),
                monotonic_cst=constraints,
                **params,
            )
            candidate.fit(x_train, y_train)
            loss = float(log_loss(y_valid, candidate.predict_proba(x_valid)[:, 1]))
            if loss < self.best_loss_:
                self.best_loss_, best_params = loss, dict(params)

        self.best_params_ = best_params
        self.clf_ = HistGradientBoostingClassifier(
            random_state=self.seed,
            categorical_features=list(CATEGORICAL_FEATURES),
            monotonic_cst=constraints,
            **cast(dict[str, Any], self.best_params_),
        )
        self.clf_.fit(x_train, y_train)
        # Calibration isotone apprise sur la validation UNIQUEMENT (jamais le test).
        self.iso_ = IsotonicRegression(out_of_bounds="clip").fit(
            self.clf_.predict_proba(x_valid)[:, 1], y_valid
        )
        numeric = [c for c in self.features_ if c not in CATEGORICAL_FEATURES]
        self.profiles_ = scenario_profiles(train, numeric, list(CATEGORICAL_FEATURES))
        self._valid_X = x_valid
        self._valid_group = valid["position_group"].cast(pl.String).to_numpy()
        return self

    # --- prédiction -------------------------------------------------------------------------

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self.clf_ is None or self.iso_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        raw = self.clf_.predict_proba(self._frame(df))[:, 1]
        calibrated = np.asarray(self.iso_.predict(raw), dtype=float)
        return np.clip(calibrated, 1e-6, 1 - 1e-6)

    def params(self) -> dict[str, Any]:
        return {
            "objective": "binary",
            "features": ",".join([*self.features_, EXPOSURE_FEATURE, *CATEGORICAL_FEATURES]),
            "exposure": "log_exposure = log(minutes_played/80), monotone croissante (offset)",
            "grid_size": len(_PARAM_GRID),
            "best_params": jsonable(self.best_params_),
            "best_valid_log_loss": self.best_loss_,
            "calibration": "isotone sur validation (IsotonicRegression)",
            "monotone": jsonable(self.monotone) or None,
            "categorical_native": ",".join(CATEGORICAL_FEATURES),
        }

    # --- interprétabilité (docs/06 §4) -------------------------------------------------------

    def report_tables(self) -> dict[str, str]:
        if self._valid_X is None or self._valid_group is None or self.clf_ is None:
            return {}
        return {
            "SHAP (moyenne |valeur|, validation)": self._shap_table(),
            "ALE consecutive_matches par groupe (validation)": self._ale_table(),
            "Courbes h(N) par poste (scénario médian, M3)": self._curve_table(),
        }

    def _shap_table(self) -> str:
        import shap  # type: ignore[import-untyped]  # noqa: PLC0415

        assert self._valid_X is not None
        sample = self._valid_X.iloc[:_SHAP_MAX_ROWS]
        values = np.asarray(
            shap.TreeExplainer(self.clf_).shap_values(_shap_numeric(sample)), dtype=float
        )
        mean_abs = np.abs(values).mean(axis=0)
        order = np.argsort(mean_abs)[::-1][:15]
        lines = ["| Feature | SHAP moyen |abs| |", "|---|---|"]
        for i in order:
            lines.append(f"| {sample.columns[i]} | {mean_abs[i]:.5f} |")
        return "\n".join(lines)

    def _ale_table(self) -> str:
        assert self._valid_X is not None and self._valid_group is not None
        j = list(self._valid_X.columns).index("consecutive_matches")

        def predict(rows: np.ndarray) -> np.ndarray:
            assert self._valid_X is not None and self.clf_ is not None
            frame = pd.DataFrame(rows, columns=self._valid_X.columns)
            return np.asarray(self.clf_.predict_proba(frame)[:, 1], dtype=float)

        lines = ["| Groupe | N (centre bin) | Effet ALE |", "|---|---|---|"]
        for group in sorted(set(self._valid_group.tolist())):
            rows = self._valid_X[self._valid_group == group].to_numpy()
            centers, effects = ale_1d(predict, rows, j, n_bins=6)
            for c, e in zip(centers, effects, strict=True):
                if np.isfinite(c):
                    lines.append(f"| {group} | {c:.1f} | {e:+.4f} |")
        return "\n".join(lines)

    def _curve_table(self) -> str:
        ns = (0, 3, 6, 9, 12, 15)
        lines = ["| Poste | " + " | ".join(f"N={n}" for n in ns) + " |", "|---|" + "---|" * len(ns)]
        for code in sorted(self.profiles_):
            h = hazard_curve(self, code, ns)
            lines.append(f"| {code} | " + " | ".join(f"{v:.4f}" for v in h) + " |")
        return "\n".join(lines)


def jsonable(value: Any) -> Any:
    import json  # noqa: PLC0415

    return json.loads(json.dumps(value, default=str))
