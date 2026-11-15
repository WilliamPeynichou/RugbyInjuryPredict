"""M1 discrete-time hazard (F20, docs/06 §1-2).

Binomial GLM on played rows, cloglog link (logit as alternative) with exposure offset
`log(minutes/80)`: cloglog(h) = eta + log(minutes/80) is a piecewise Poisson process with a
per-full-match rate. Splines and position x load interactions come from `DesignSpec`; every
transformation is learned on the training fold only (`design.build_design`).

Selection correction (IPW, F21): `fit(..., sample_weight=...)` accepts per-row
stabilized inverse-probability weights (`modeling/selection.py`). They enter the GLM as a
weighted Bernoulli likelihood via the grouped binomial form `endog = [y*w, (1-y)*w]`: statsmodels
0.15 `freq_weights` demonstrably leaves Bernoulli coefficients unchanged (checked against
row duplication, journal F21), so the 2-column form is used instead. Weights follow the rows
in the player-cluster bootstrap of the curves.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl
import statsmodels.api as sm

from rugby_risk.features.registry import FEATURES
from rugby_risk.modeling.curves import (
    SCENARIOS_PATH,
    Scenarios,
    cumulative_risk,
    hazard_curve,
    load_scenarios,
    scenario_profiles,
)
from rugby_risk.modeling.design import Design, DesignSpec, FittedTransform, build_design

LINKS: Final = {"cloglog": sm.families.links.CLogLog, "logit": sm.families.links.Logit}
DEFAULT_CURVE_REPLICATIONS: Final = 200
CUMULATIVE_HORIZON: Final = 5  # risque cumulé affiché sur 5 matchs
_TABLE_NS: Final = (0, 3, 6, 9, 12, 15)
_CI_LEVEL: Final = 0.90


@dataclass
class _Bands:
    """Bootstrap percentile bands of the median-scenario curves, by position."""

    low: dict[str, np.ndarray] = field(default_factory=dict)
    high: dict[str, np.ndarray] = field(default_factory=dict)
    replications: int = 0
    failures: int = 0


class DiscreteHazardModel:
    """M1: GLM binomial (cloglog | logit) + offset, implements `RiskModel` (F18)."""

    def __init__(
        self,
        link: str = "cloglog",
        spec: DesignSpec | None = None,
        curve_replications: int = DEFAULT_CURVE_REPLICATIONS,
        seed: int = 0,
        scenarios_path: Path = SCENARIOS_PATH,
    ) -> None:
        if link not in LINKS:
            raise ValueError(f"Lien inconnu : {link} (connus : {sorted(LINKS)})")
        self.link = link
        self.name = f"m1_hazard_{link}"
        self.spec = spec or DesignSpec()
        self.curve_replications = curve_replications
        self.seed = seed
        self.scenarios_path = scenarios_path
        self.result_: Any = None
        self.transform_: FittedTransform | None = None
        self.columns_: tuple[str, ...] = ()
        self.profiles_: dict[str, dict[str, Any]] = {}
        self.scenarios_: Scenarios = load_scenarios(scenarios_path)
        self._train: pl.DataFrame | None = None
        self._train_weights: np.ndarray | None = None
        self._bands: _Bands | None = None
        self._check_scenarios()

    @property
    def weighted_(self) -> bool:
        return self._train_weights is not None

    def _check_scenarios(self) -> None:
        # Contre le registre (pas la spec) : typo détectée, spec réduite tolérée.
        allowed = set(FEATURES)
        for name, overrides in self.scenarios_.overrides.items():
            unknown = sorted(set(overrides) - allowed)
            if unknown:
                raise ValueError(f"Scénario {name} : colonnes hors design {unknown}")

    def _glm(self, design: Design, sample_weight: np.ndarray | None = None) -> Any:
        family = sm.families.Binomial(link=LINKS[self.link]())
        if sample_weight is None:
            return sm.GLM(design.y, design.X, family=family, offset=design.offset).fit()
        # Vraisemblance de Bernoulli pondérée via la forme binomiale groupée :
        # endog = [y*w, (1-y)*w] reproduit exactement le MLE pondéré (statsmodels 0.15
        # ignore freq_weights pour les coefficients Bernoulli, cf. module docstring).
        w = np.asarray(sample_weight, dtype=float)
        y = design.y
        if y is None:
            raise ValueError(f"Cible absente du train : {self.spec.target}")
        endog = np.column_stack([y * w, (1.0 - y) * w])
        return sm.GLM(endog, design.X, family=family, offset=design.offset).fit()

    def fit(
        self,
        train: pl.DataFrame,
        valid: pl.DataFrame | None = None,
        sample_weight: np.ndarray | None = None,
    ) -> "DiscreteHazardModel":
        del valid  # pas d'hyperparamètre : la saison de validation n'est pas utilisée
        design = build_design(train, self.spec)
        if design.y is None:
            raise ValueError(f"Cible absente du train : {self.spec.target}")
        if sample_weight is not None and len(sample_weight) != len(train):
            raise ValueError("sample_weight doit avoir une valeur par ligne du train")
        self.result_ = self._glm(design, sample_weight)
        self.transform_ = design.transform
        self.columns_ = design.columns
        self._train_weights = (
            None if sample_weight is None else np.asarray(sample_weight, dtype=float)
        )
        self.transform_ = design.transform
        self.columns_ = design.columns
        source = self.spec.source_columns()
        self.profiles_ = scenario_profiles(
            train,
            [c for c in source if c not in self.spec.categorical],
            [c for c in source if c in self.spec.categorical],
        )
        self._train = train
        self._bands = None
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self.result_ is None or self.transform_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        design = build_design(df, self.spec, self.transform_)
        return np.asarray(self.result_.predict(design.X, offset=design.offset), dtype=float)

    def coefficients(self, alpha: float = 0.05) -> pl.DataFrame:
        """Coefficients on the standardised scale with Wald (1 - alpha) intervals."""
        if self.result_ is None:
            raise RuntimeError("fit() doit être appelé avant coefficients()")
        ci = np.asarray(self.result_.conf_int(alpha=alpha))
        return pl.DataFrame(
            {
                "term": list(self.columns_),
                "coef": np.asarray(self.result_.params, dtype=float),
                "se": np.asarray(self.result_.bse, dtype=float),
                "low": ci[:, 0],
                "high": ci[:, 1],
            }
        )

    def params(self) -> dict[str, Any]:
        t = self.transform_
        return {
            "link": self.link,
            "offset": "log(minutes_played/80)",
            "formula": t.formula if t else None,
            "dropped_terms": ",".join(t.dropped) if t else None,
            "n_params": len(self.columns_),
            "converged": bool(self.result_.converged) if self.result_ is not None else None,
            "aic": float(self.result_.aic) if self.result_ is not None else None,
            "curve_replications": self.curve_replications,
            "weighted_ipw": self.weighted_,
        }

    # --- rapport -------------------------------------------------------------------------

    def _curve_bands(self) -> _Bands:
        """Player-cluster bootstrap of the median curves (refit on resampled players)."""
        if self._bands is not None:
            return self._bands
        bands = _Bands()
        train = self._train
        weights = self._train_weights
        if train is None or self.curve_replications <= 0:
            self._bands = bands
            return bands
        keys = train["player_key"].to_numpy()
        players, inverse = np.unique(keys, return_inverse=True)
        rows_of = [np.flatnonzero(inverse == i) for i in range(len(players))]
        rng = np.random.default_rng(self.seed)
        draws: dict[str, list[np.ndarray]] = {code: [] for code in self.profiles_}
        for _ in range(self.curve_replications):
            picked = rng.choice(len(players), size=len(players), replace=True)
            rows = np.concatenate([rows_of[i] for i in picked])
            sample = train[rows]
            replica = DiscreteHazardModel(self.link, self.spec, 0, self.seed, self.scenarios_path)
            try:
                replica.fit(sample, sample_weight=None if weights is None else weights[rows])
                curves = {code: hazard_curve(replica, code) for code in draws}
            except (ValueError, KeyError, np.linalg.LinAlgError):
                bands.failures += 1  # poste absent du rééchantillon, matrice singulière
                continue
            for code, curve in curves.items():
                draws[code].append(curve)
        lo_q, hi_q = (1 - _CI_LEVEL) / 2, (1 + _CI_LEVEL) / 2
        for code, replicas in draws.items():
            if replicas:
                stacked = np.vstack(replicas)
                bands.low[code] = np.quantile(stacked, lo_q, axis=0)
                bands.high[code] = np.quantile(stacked, hi_q, axis=0)
        bands.replications = self.curve_replications - bands.failures
        self._bands = bands
        return bands

    def _alternate_aic(self) -> tuple[str, float] | None:
        """AIC of the other link on the same training design (in-sample comparison).

        Indisponible pour le modèle pondéré : l'AIC groupée (log-vraisemblance pondérée)
        n'est pas comparable à celle d'un fit non pondéré."""
        if self._train is None or self.transform_ is None or self.weighted_:
            return None
        other = "logit" if self.link == "cloglog" else "cloglog"
        design = build_design(self._train, self.spec)
        family = sm.families.Binomial(link=LINKS[other]())
        result = sm.GLM(design.y, design.X, family=family, offset=design.offset).fit()
        return other, float(result.aic)

    def report_tables(self) -> dict[str, str]:
        if self.result_ is None:
            return {}
        coefs = self.coefficients()
        coef_lines = ["| Terme | Coef | SE | IC95 % |", "|---|---|---|---|"]
        coef_lines += [
            f"| {r['term']} | {r['coef']:.3f} | {r['se']:.3f} | [{r['low']:.3f}; {r['high']:.3f}] |"
            for r in coefs.iter_rows(named=True)
        ]
        dropped = self.transform_.dropped if self.transform_ else ()
        coef_lines.append(
            "\nVariables continues standardisées (moyenne/écart-type du train), binaires en 0/1."
            " Termes écartés (constants/support insuffisant au train) :"
            f" {', '.join(dropped) or '-'}."
        )
        bands = self._curve_bands()
        ns = self.scenarios_.n_range
        idx = [ns.index(n) for n in _TABLE_NS if n in ns]
        header = " | ".join(f"N={ns[i]}" for i in idx)
        curve_lines = [
            f"| Poste | {header} | Cumulé {CUMULATIVE_HORIZON} |",
            "|---|" + "---|" * (len(idx) + 1),
        ]
        scenario_lines = [
            "| Poste | " + " | ".join(self.scenarios_.overrides) + " |",
            "|---|" + "---|" * len(self.scenarios_.overrides),
        ]
        for code in sorted(self.profiles_):
            h = hazard_curve(self, code)
            cells = []
            for i in idx:
                band = (
                    f" [{bands.low[code][i]:.4f}; {bands.high[code][i]:.4f}]"
                    if code in bands.low
                    else ""
                )
                cells.append(f"{h[i]:.4f}{band}")
            cum = cumulative_risk(h[:CUMULATIVE_HORIZON])
            curve_lines.append(f"| {code} | " + " | ".join(cells) + f" | {cum:.3f} |")
            per_scenario = [
                cumulative_risk(hazard_curve(self, code, scenario=s)[:CUMULATIVE_HORIZON])
                for s in self.scenarios_.overrides
            ]
            scenario_lines.append(
                f"| {code} | " + " | ".join(f"{v:.3f}" for v in per_scenario) + " |"
            )
        mention = (
            " Pondération IPW (F21)."
            if self.weighted_
            else " Association, pas causalité ; sans correction de sélection (F21)."
        )
        curve_lines.append(
            f"\nh(N) = P(blessure au match suivant | N matchs consécutifs), 80 min, profil médian"
            f" du poste. IC{int(_CI_LEVEL * 100)} bootstrap joueur"
            f" ({bands.replications} réplications, {bands.failures} échecs)." + mention
        )
        tables = {
            f"M1 ({self.link}) : coefficients": "\n".join(coef_lines),
            "Courbes h(N) par poste (scénario médian)": "\n".join(curve_lines),
            f"Risque cumulé sur {CUMULATIVE_HORIZON} matchs par scénario": "\n".join(
                scenario_lines
            ),
        }
        alternate = self._alternate_aic()
        if alternate is not None:
            other, aic = alternate
            tables["Comparaison des liens (train, in-sample)"] = (
                "| Lien | AIC |\n|---|---|\n"
                f"| {self.link} | {self.result_.aic:.1f} |\n| {other} | {aic:.1f} |\n\n"
                "Comparaison hors échantillon : rapports m1_hazard_cloglog vs m1_hazard_logit."
            )
        return tables

    def report_figures(self, directory: Path, run_id: str) -> list[Path]:
        """h(N) curves by position (median scenario) with bootstrap bands."""
        if self.result_ is None:
            return []
        import matplotlib.pyplot as plt  # noqa: PLC0415 - backend Agg fixé par le runner

        bands = self._curve_bands()
        ns = np.asarray(self.scenarios_.n_range)
        fig, ax = plt.subplots(figsize=(8, 5))
        for code in sorted(self.profiles_):
            (line,) = ax.plot(ns, hazard_curve(self, code), label=code)
            if code in bands.low:
                ax.fill_between(
                    ns, bands.low[code], bands.high[code], color=line.get_color(), alpha=0.12
                )
        ax.set_xlabel("N matchs consécutifs")
        ax.set_ylabel("h(N) : P(blessure au match suivant, 80 min)")
        ax.set_title(f"{self.name} - courbes h(N), scénario médian")
        ax.legend(fontsize="small", ncol=3)
        fig.tight_layout()
        path = directory / f"{run_id}_hazard_curves.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return [path]
