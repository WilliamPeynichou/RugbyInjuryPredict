"""Selection model and IPW weights (F21, docs/06 §1, §3.3).

Two sub-problems (docs/06 §1): P(played) then P(injury | played). The first is modelled here
on ALL eligible rows (played or not) with as-of features only; its cross-fitted predictions
pi_hat feed stabilized inverse-probability weights `w = P(played) / pi_hat` (truncated at
train quantiles) applied to the played rows of the hazard GLM (`DiscreteHazardModel.fit(
sample_weight=...)`) -> M1w.

Known non-injury absences (international duty, suspension) are NOT identifiable in
`ml_player_match` today (`fact_eligibility.absence_reason` is a null placeholder) : the
selection design uses `intl_window` and `protected_list` as observed proxies for duty, and
suspension is listed as a data gap (docs/10). Exclusion vs covariate choice is argued in the
feature journal: covariates, because the alternative would require a per-match absence_reason
in the ml mart (out of F21 scope).

Calibration gate (feature spec): the selection model's cross-fitted calibration slope must lie
in [0.8, 1.2] before the weights are used; otherwise IPW is disabled for the fold and a
warning is reported.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder

from rugby_risk.features.registry import (
    FORBIDDEN_COLUMNS,
    ID_COLUMNS,
    TARGET_AND_EXPOSURE_COLUMNS,
)
from rugby_risk.modeling.design import DesignSpec
from rugby_risk.modeling.hazard import DiscreteHazardModel

SLOPE_BOUNDS: Final = (0.8, 1.2)
DEFAULT_CALIBRATION_FOLDS: Final = 5
_MIN_STD: Final = 1e-12


@dataclass(frozen=True)
class SelectionSpec:
    """As-of features of the selection model (columns of `ml_player_match`)."""

    numeric: tuple[str, ...] = (
        "consecutive_matches",
        "consecutive_starts",
        "min_7d",
        "min_28d",
        "apps_20min_365d",
        "days_since_last_match",
        "season_round_index",
        "weeks_without_rest",
        "age",
        "short_turnaround",
        "intl_window",
        "protected_list",
        "recent_return_8w",
        "n_prior_injuries_365d",
        "days_since_return",
        "opponent_strength",
    )
    categorical: tuple[str, ...] = ("position_group", "unit", "is_home")
    C: float = 1.0  # régularisation L2 (sklearn : inverse de la force)
    calibration_folds: int = DEFAULT_CALIBRATION_FOLDS
    seed: int = 0

    def source_columns(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([*self.numeric, *self.categorical]))

    def validate(self) -> None:
        banned = set(TARGET_AND_EXPOSURE_COLUMNS) | set(ID_COLUMNS) | set(FORBIDDEN_COLUMNS)
        leaked = sorted(set(self.source_columns()) & banned)
        if leaked:
            raise ValueError(f"Colonnes interdites dans le modèle de sélection : {leaked}")
        from rugby_risk.features.registry import FEATURES  # noqa: PLC0415

        unknown = sorted(set(self.source_columns()) - set(FEATURES))
        if unknown:
            raise ValueError(f"Colonnes hors registre FEATURES : {unknown}")


@dataclass(frozen=True)
class WeightDiagnostics:
    """Everything needed to audit the IPW step of one fold."""

    n: int
    slope: float
    slope_ok: bool
    ipw_enabled: bool
    stabilized: bool
    truncate_lo: float
    truncate_hi: float
    weight_median: float
    weight_p01: float
    weight_p99: float
    weight_max: float
    ess: float
    ess_ratio: float

    def as_row(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "pente calib. sélection": f"{self.slope:.3f}",
            "pente ok": self.slope_ok,
            "IPW actif": self.ipw_enabled,
            "stabilisé": self.stabilized,
            "troncature": f"[{self.truncate_lo:.2f}; {self.truncate_hi:.2f}]",
            "w médian": f"{self.weight_median:.3f}",
            "w p01/p99": f"{self.weight_p01:.3f} / {self.weight_p99:.3f}",
            "w max": f"{self.weight_max:.3f}",
            "ESS": f"{self.ess:.0f}",
            "ESS/n": f"{self.ess_ratio:.3f}",
        }


class SelectionModel:
    """Regularized logistic regression of `played` on as-of features.

    Transformations (numeric medians/means/stds, categorical levels) are learned on the
    training fold only and re-applied verbatim elsewhere — same purity rule as
    `modeling/design.py`.
    """

    def __init__(self, spec: SelectionSpec | None = None) -> None:
        self.spec = spec or SelectionSpec()
        self.spec.validate()
        self.model_ = LogisticRegression(C=self.spec.C, max_iter=1000)
        self.medians_: dict[str, float] = {}
        self.means_: dict[str, float] = {}
        self.stds_: dict[str, float] = {}
        self.levels_: dict[str, tuple[str, ...]] = {}

    def _matrix(self, df: pl.DataFrame) -> np.ndarray:
        blocks: list[np.ndarray] = []
        if self.spec.numeric:
            num = df.select(
                [
                    pl.col(c).cast(pl.Float64).fill_null(self.medians_[c]).alias(c)
                    for c in self.spec.numeric
                ]
            )
            arr = np.column_stack(
                [(num[c].to_numpy() - self.means_[c]) / self.stds_[c] for c in self.spec.numeric]
            )
            blocks.append(arr)
        if self.spec.categorical:
            # Modalité inconnue au test -> modalité la plus fréquente du train (référence),
            # même convention que modeling/design.py.
            mapped = []
            for c in self.spec.categorical:
                levels = self.levels_[c]
                fallback = levels[0]
                values = df[c].cast(pl.String).fill_null("unknown").to_list()
                mapped.append(np.array([v if v in levels else fallback for v in values]))
            cats = np.column_stack(mapped)
            encoder = OneHotEncoder(
                categories=[list(self.levels_[c]) for c in self.spec.categorical],
                drop="first",
                handle_unknown="ignore",
                sparse_output=False,
            )
            blocks.append(np.asarray(encoder.fit_transform(cats), dtype=float))
        return np.column_stack(blocks) if blocks else np.empty((len(df), 0))

    def fit(self, eligible: pl.DataFrame) -> "SelectionModel":
        """`eligible`: every eligible row (played or not) of the training seasons."""
        missing = [c for c in self.spec.source_columns() if c not in eligible.columns]
        if missing:
            raise ValueError(f"Colonnes absentes du frame éligible : {missing}")
        y = eligible.get_column("played").cast(pl.Float64).to_numpy()
        if len(np.unique(y)) < 2:  # noqa: PLR2004 - une seule classe : pas de sélection à modéliser
            raise ValueError("played est constant sur le train : modèle de sélection impossible")
        for c in self.spec.numeric:
            s = eligible.get_column(c).cast(pl.Float64)
            median = float(s.median()) if s.drop_nulls().len() > 0 else 0.0  # type: ignore[arg-type]
            filled = s.fill_null(median).to_numpy()
            std = float(filled.std())
            self.medians_[c] = median
            self.means_[c] = float(filled.mean())
            self.stds_[c] = std if std > _MIN_STD else 1.0
        for c in self.spec.categorical:
            counts = (
                eligible.get_column(c).cast(pl.String).fill_null("unknown").value_counts(sort=True)
            )
            values = tuple(str(v) for v in counts[counts.columns[0]].to_list())
            if len(values) < 2:  # noqa: PLR2004
                raise ValueError(f"Catégorie constante dans le modèle de sélection : {c}")
            self.levels_[c] = values
        self.model_.fit(self._matrix(eligible), y)
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if not hasattr(self.model_, "coef_"):
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        return np.asarray(self.model_.predict_proba(self._matrix(df))[:, 1], dtype=float)

    def calibration_slope_cv(self, eligible: pl.DataFrame) -> float:
        """Slope of logit(y) on cross-fitted logit(pi), blocs contigus (pas de mélange).

        Contiguous blocked cross-fitting (train on all blocks but one, predict the held-out
        block) : deterministic, respects row order. In-sample slope of a regularized fit is
        biased toward 1 ; the cross-fitted slope is the honest gate for using the weights.
        """
        y = eligible.get_column("played").cast(pl.Float64).to_numpy()
        x = self._matrix(eligible)
        blocks = np.array_split(np.arange(len(y)), min(self.spec.calibration_folds, len(y)))
        pi = np.empty(len(y), dtype=float)
        for block in blocks:
            mask = np.ones(len(y), dtype=bool)
            mask[block] = False
            block_model = LogisticRegression(C=self.spec.C, max_iter=1000).fit(x[mask], y[mask])
            pi[block] = np.asarray(block_model.predict_proba(x[block])[:, 1], dtype=float)
        logit = np.log(np.clip(pi, 1e-6, 1 - 1e-6) / (1 - np.clip(pi, 1e-6, 1 - 1e-6)))
        slope_fit = LogisticRegression(max_iter=1000).fit(logit.reshape(-1, 1), y)
        return float(np.asarray(slope_fit.coef_, dtype=float)[0, 0])


def stabilized_weights(
    pi: np.ndarray,
    positions: np.ndarray,
    *,
    stabilize: bool,
    position_rates: dict[str, float] | None,
    truncate: tuple[float, float],
) -> tuple[np.ndarray, WeightDiagnostics]:
    """IPW weights for played rows + diagnostics (docs/06 §1).

    `w = P(played) / pi` with P(played) estimated per position on the ELIGIBLE training
    rows (`position_rates`, same fold) when `stabilize`, else `w = 1 / pi`. Truncation at
    the `truncate` quantiles of w (e.g. (0.01, 0.99)); ESS = (sum w)^2 / sum w^2.
    """
    pi = np.clip(np.asarray(pi, dtype=float), 1e-6, 1.0)
    if stabilize:
        if not position_rates:
            raise ValueError("Stabilisation : position_rates (éligible) requis")
        try:
            numerator = np.array([position_rates[str(p)] for p in positions], dtype=float)
        except KeyError as exc:
            raise ValueError(f"Poste absent des taux éligibles : {exc}") from exc
    else:
        numerator = np.ones(len(pi), dtype=float)
    w = numerator / pi
    lo, hi = (float(np.quantile(w, q)) for q in truncate)
    w = np.clip(w, lo, hi)
    ess = float(w.sum() ** 2 / (w**2).sum())
    diagnostics = WeightDiagnostics(
        n=len(w),
        slope=float("nan"),  # renseigné par l'appelant (gate de calibration)
        slope_ok=False,
        ipw_enabled=False,
        stabilized=stabilize,
        truncate_lo=lo,
        truncate_hi=hi,
        weight_median=float(np.median(w)),
        weight_p01=float(np.quantile(w, 0.01)),
        weight_p99=float(np.quantile(w, 0.99)),
        weight_max=float(w.max()),
        ess=ess,
        ess_ratio=ess / len(w),
    )
    return w, diagnostics


class WeightedHazardModel:
    """M1w : M1 hazard + IPW selection correction (F21).

    Pipeline per training fold: selection model fit on ALL eligible rows of the fold,
    calibration gate on the cross-fitted slope, stabilized truncated weights on the played
    rows, then the weighted hazard GLM. An unweighted M1 is refit on the same rows so the
    report can compare load coefficients and h(N) curves directly.
    """

    requires_eligible = True

    def __init__(  # noqa: PLR0913 - hyperparamètres du pipeline M1w (même profil que M1)
        self,
        link: str = "cloglog",
        curve_replications: int = 200,
        seed: int = 0,
        *,
        stabilize: bool = True,
        truncate: tuple[float, float] = (0.01, 0.99),
        selection: SelectionSpec | None = None,
        spec: DesignSpec | None = None,
        name: str | None = None,
    ) -> None:
        # Un nom par variante : évite les collisions de nom de rapport quand deux
        # variantes finissent dans la même seconde (run_id = f"{name}-{timestamp}").
        self.name = name or "m1w_hazard_ipw"
        self.link = link
        self.curve_replications = curve_replications
        self.seed = seed
        self.stabilize = stabilize
        self.truncate = truncate
        self.selection_spec = selection or SelectionSpec(seed=seed)
        self.spec = spec or DesignSpec()
        self.selection_: SelectionModel | None = None
        self.diagnostics_: WeightDiagnostics | None = None
        self.warning_: str | None = None
        self.hazard_: DiscreteHazardModel | None = None
        self._ref: DiscreteHazardModel | None = None

    def fit(
        self,
        train: pl.DataFrame,
        valid: pl.DataFrame | None = None,
        eligible: pl.DataFrame | None = None,
    ) -> "WeightedHazardModel":
        if eligible is None:
            raise ValueError("M1w exige le frame éligible (runner, requires_eligible)")
        self.selection_ = SelectionModel(self.selection_spec).fit(eligible)
        slope = self.selection_.calibration_slope_cv(eligible)
        pi = self.selection_.predict_proba(train)
        positions = train.get_column("position_group").cast(pl.String).to_numpy()
        rates = (
            eligible.group_by("position_group")
            .agg(pl.col("played").cast(pl.Float64).mean().alias("rate"))
            .select(
                [
                    pl.col("position_group").cast(pl.String).alias("pos"),
                    pl.col("rate"),
                ]
            )
        )
        position_rates = {r["pos"]: float(r["rate"]) for r in rates.iter_rows(named=True)}
        w, diagnostics = stabilized_weights(
            pi,
            positions,
            stabilize=self.stabilize,
            position_rates=position_rates,
            truncate=self.truncate,
        )
        lo, hi = SLOPE_BOUNDS
        slope_ok = lo <= slope <= hi
        ipw_enabled = slope_ok
        if not slope_ok:
            self.warning_ = (
                f"Pente de calibration de la sélection = {slope:.3f} hors [{lo}; {hi}]"
                " : IPW désactivé pour ce fold (poids = 1)."
            )
            w = np.ones(len(train), dtype=float)
        self.diagnostics_ = WeightDiagnostics(
            n=diagnostics.n,
            slope=slope,
            slope_ok=slope_ok,
            ipw_enabled=ipw_enabled,
            stabilized=diagnostics.stabilized,
            truncate_lo=diagnostics.truncate_lo,
            truncate_hi=diagnostics.truncate_hi,
            weight_median=diagnostics.weight_median,
            weight_p01=diagnostics.weight_p01,
            weight_p99=diagnostics.weight_p99,
            weight_max=diagnostics.weight_max,
            ess=diagnostics.ess,
            ess_ratio=diagnostics.ess_ratio,
        )
        self._ref = DiscreteHazardModel(
            self.link, spec=self.spec, curve_replications=0, seed=self.seed
        ).fit(train, valid)
        self.hazard_ = DiscreteHazardModel(
            self.link, spec=self.spec, curve_replications=self.curve_replications, seed=self.seed
        ).fit(train, valid, sample_weight=w if ipw_enabled else None)
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self.hazard_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        return self.hazard_.predict_proba(df)

    def params(self) -> dict[str, Any]:
        d = self.diagnostics_
        return {
            "link": self.link,
            "ipw_stabilized": self.stabilize,
            "ipw_truncate_lo": self.truncate[0],
            "ipw_truncate_hi": self.truncate[1],
            "selection_C": self.selection_spec.C,
            "selection_features": len(self.selection_spec.source_columns()),
            "ipw_enabled": d.ipw_enabled if d else None,
            "selection_slope": d.slope if d else None,
            "weight_ess_ratio": d.ess_ratio if d else None,
            "warning": self.warning_,
        }

    def _diagnostics_table(self) -> str:
        d = self.diagnostics_
        if d is None:
            return ""
        keys = list(d.as_row())
        header = "| " + " | ".join(keys) + " |"
        row = "| " + " | ".join(str(v) for v in d.as_row().values()) + " |"
        sep = "|" + "---|" * len(keys)
        note = (
            "\n\nPoids IPW stabilisés w = P(played|poste)/π̂ tronqués aux quantiles du train,"
            " appliqués aux lignes jouées du GLM (forme binomiale groupée, S13). Gate : pente"
            " de calibration"
            " de la sélection (cross-fittée) dans [0,8 ; 1,2], sinon IPW désactivé pour le fold."
            " Suspensions non identifiables dans ml_player_match (absence_reason non matérialisé,"
            " docs/10) ; proxies observés : intl_window, protected_list."
        )
        if self.warning_:
            note += f"\n\n⚠ {self.warning_}"
        return header + "\n" + sep + "\n" + row + note

    def _comparison_table(self) -> str:
        if self._ref is None or self.hazard_ is None:
            return ""
        ref = self._ref.coefficients()
        weighted = self.hazard_.coefficients()
        joined = weighted.join(ref, on="term", suffix="_ref")
        load = joined.filter(
            pl.col("term").str.contains("consecutive_matches")
            | pl.col("term").str.contains("min_28d")
        )
        lines = [
            "| Terme | Coef M1 | Coef M1w (IPW) | Δ |",
            "|---|---|---|---|",
        ]
        for r in load.iter_rows(named=True):
            delta = r["coef"] - r["coef_ref"]
            lines.append(f"| {r['term']} | {r['coef_ref']:.3f} | {r['coef']:.3f} | {delta:+.3f} |")
        lines.append(
            "\nCoefficients (log-HR) des termes de charge, M1 non pondéré vs M1w, même fold"
            " d'estimation. Un Δ > 0 après IPW = effet de charge revu à la hausse quand le"
            " biais du survivant est corrigé. Association, pas causalité."
        )
        return "\n".join(lines)

    def report_tables(self) -> dict[str, str]:
        if self.hazard_ is None:
            return {}
        tables = {
            "Diagnostics IPW (modèle de sélection, train du fold)": self._diagnostics_table(),
            "M1 vs M1w : coefficients de charge": self._comparison_table(),
        }
        tables.update(self.hazard_.report_tables())
        return tables

    def report_figures(self, directory: Path, run_id: str) -> list[Path]:
        """h(N) curves by position, unweighted M1 (dashed) vs M1w (solid), median scenario."""
        if self._ref is None or self.hazard_ is None:
            return []
        import matplotlib.pyplot as plt  # noqa: PLC0415 - backend Agg fixé par le runner

        from rugby_risk.modeling.curves import hazard_curve  # noqa: PLC0415

        ns = np.asarray(self.hazard_.scenarios_.n_range)
        fig, ax = plt.subplots(figsize=(8, 5))
        codes = sorted(self.hazard_.profiles_)
        for code in codes:
            (line,) = ax.plot(ns, hazard_curve(self.hazard_, code), label=f"{code} (M1w)")
            ax.plot(
                ns,
                hazard_curve(self._ref, code),
                linestyle="--",
                color=line.get_color(),
                label=f"{code} (M1)",
            )
        ax.set_xlabel("N matchs consécutifs")
        ax.set_ylabel("h(N) : P(blessure au match suivant, 80 min)")
        ax.set_title(f"{self.name} - courbes h(N), scénario médian, M1 vs M1w")
        ax.legend(fontsize="small", ncol=2)
        fig.tight_layout()
        path = directory / f"{run_id}_hazard_curves_ipw.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return [path]
