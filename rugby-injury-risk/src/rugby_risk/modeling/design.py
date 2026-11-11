"""Design matrix for M1 hazard models (F20, docs/06 §1-2).

`build_design(df, spec, fitted=None)` is pure: on the training fold it learns every
transformation (imputation medians, standardisation, category levels, spline knots, dropped
degenerate terms) and returns them as a `FittedTransform`; on any other fold it re-applies that
transform verbatim. No statistic is ever computed on validation or test rows (no leakage).

Degenerate terms (all-null, constant, single level on the train fold) are dropped and listed in
`FittedTransform.dropped`: on the real 2022-2025 table `age`, `surface`, `season_period`,
`short_turnaround` and `prior_concussions_365d` are constant (data gaps, docs/10).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import pandas as pd
import patsy
import polars as pl

from rugby_risk.features.registry import (
    FORBIDDEN_COLUMNS,
    ID_COLUMNS,
    TARGET_AND_EXPOSURE_COLUMNS,
)

EXPOSURE_REF_MINUTES: Final = 80.0  # offset log(minutes/80) : hazard par match complet
DAYS_CAP: Final = 60.0  # days_since_last_match plafonné (999 = pas d'historique)
# days_since_last_injury : 999 = sentinelle « jamais blessé » (coalesce dbt, int_ml_feat_
# injury_history). Elle n'est JAMAIS lue comme un nombre de jours : un indicateur porte le
# « jamais blessé », et log1p(jours) n'existe que pour les blessés (0 sinon).
INJURY_NEVER_SENTINEL: Final = 999.0
# Plafond des jours avant log1p : au-delà d'un an, l'effet d'une blessure ancienne est sature.
INJURY_LOG_CAP_DAYS: Final = 365.0
_MIN_STD: Final = 1e-12


@dataclass(frozen=True)
class DesignSpec:
    """Terms of the M1 formula (features/F20). Column names refer to `ml_player_match`."""

    categorical: tuple[str, ...] = ("position_group", "surface", "season_period")
    splines: tuple[tuple[str, int], ...] = (
        ("consecutive_matches", 4),
        ("min_28d", 3),
        ("apps_20min_365d", 3),
        ("days_since_last_match_capped", 3),
        ("age", 3),
    )
    linear: tuple[str, ...] = (
        "short_turnaround",
        "intl_window",
        "recent_return_8w",
        "n_prior_injuries_365d",
        "prior_concussions_365d",
        "is_playoff",
    )
    interactions: tuple[tuple[str, str], ...] = (
        ("position_group", "consecutive_matches"),
        ("position_group", "min_28d"),
    )
    target: str = "y_injury"
    exposure: str = "minutes_played"
    standardize: bool = True
    # Winsorisation des variables non binaires aux quantiles du train (queues rares :
    # consecutive_matches > 20 = 0,4 % des lignes, extrapolation des splines instable).
    clip_quantile: float = 0.99
    # Variable binaire écartée si sa modalité minoritaire a moins de N lignes au train
    # (quasi-séparation : coefficient infini, IC dégénéré).
    min_binary_support: int = 30

    @property
    def numeric(self) -> tuple[str, ...]:
        cols = [c for c, _ in self.splines] + list(self.linear)
        cols += [x for _, x in self.interactions if x not in cols]
        return tuple(dict.fromkeys(cols))

    def source_columns(self) -> tuple[str, ...]:
        """Columns read from the input frame (derived columns mapped to their source)."""
        cols = [_DERIVED.get(c, (c,))[0] for c in self.numeric]
        cols += list(self.categorical)
        return tuple(dict.fromkeys(cols))


def _ever_injured(s: pl.Expr) -> pl.Expr:
    """1 si un antécédent de blessure existe (sentinelle exacte 999 = jamais), 0 sinon."""
    days = s.cast(pl.Float64)
    return (
        pl.when(days.is_null())
        .then(None)
        .otherwise((days != INJURY_NEVER_SENTINEL).cast(pl.Float64))
    )


def _log_days_since_injury(s: pl.Expr) -> pl.Expr:
    """log1p(jours, plafonnés) pour un blessé ; 0 pour « jamais blessé » (sentinelle)."""
    days = s.cast(pl.Float64)
    capped = days.clip(lower_bound=0.0, upper_bound=INJURY_LOG_CAP_DAYS).log1p()
    injured = days != INJURY_NEVER_SENTINEL
    return pl.when(days.is_null()).then(None).when(injured).then(capped).otherwise(0.0)


# derived column -> (source column, transformation)
_DERIVED: Final[dict[str, tuple[str, Callable[[pl.Expr], pl.Expr]]]] = {
    "days_since_last_match_capped": (
        "days_since_last_match",
        lambda s: s.cast(pl.Float64).clip(upper_bound=DAYS_CAP),
    ),
    # Variante injhist (M2) : historique de blessure, sentinelle jamais lue en jours.
    "ever_injured": ("days_since_last_injury", _ever_injured),
    "log1p_days_since_injury": ("days_since_last_injury", _log_days_since_injury),
}


@dataclass(frozen=True)
class FittedTransform:
    """Everything learned on the training fold, re-applied unchanged elsewhere."""

    formula: str
    dropped: tuple[str, ...]
    linearised: tuple[str, ...]  # splines downgraded to linear (too few distinct values)
    medians: dict[str, float]
    bounds: dict[str, tuple[float, float]]
    means: dict[str, float]
    stds: dict[str, float]
    levels: dict[str, tuple[str, ...]]
    design_info: Any  # patsy.DesignInfo (knots of the splines live here)


@dataclass(frozen=True)
class Design:
    X: np.ndarray
    columns: tuple[str, ...]
    offset: np.ndarray
    y: np.ndarray | None
    transform: FittedTransform


def validate_spec(spec: DesignSpec) -> None:
    """Targets, exposure of match t and identifiers never enter the design (offset excepted)."""
    banned = set(TARGET_AND_EXPOSURE_COLUMNS) | set(ID_COLUMNS) | FORBIDDEN_COLUMNS
    leaked = sorted(set(spec.source_columns()) & banned)
    if leaked:
        raise ValueError(f"Colonnes interdites dans le design (fuite/identifiant) : {leaked}")


def _numeric_frame(df: pl.DataFrame, spec: DesignSpec) -> pl.DataFrame:
    exprs = []
    for col in spec.numeric:
        if col in _DERIVED:
            source, fn = _DERIVED[col]
            exprs.append(fn(pl.col(source)).alias(col))
        else:
            exprs.append(pl.col(col).cast(pl.Float64).alias(col))
    return df.select(exprs)


def _learn(num: pl.DataFrame, cats: pl.DataFrame, spec: DesignSpec) -> dict[str, Any]:
    dropped: list[str] = []
    linearised: list[str] = []
    medians: dict[str, float] = {}
    bounds: dict[str, tuple[float, float]] = {}
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    spline_df = dict(spec.splines)
    for col in num.columns:
        s = num[col].drop_nulls()
        if s.is_empty():
            dropped.append(col)
            continue
        median = float(s.median())  # type: ignore[arg-type]
        filled = num[col].fill_null(median).to_numpy()
        distinct, counts = np.unique(filled, return_counts=True)
        if len(distinct) < 2 or (  # noqa: PLR2004 - constante ou binaire
            len(distinct) == 2 and counts.min() < spec.min_binary_support  # noqa: PLR2004
        ):
            dropped.append(col)
            continue
        lo, hi = (
            (float(distinct[0]), float(distinct[-1]))
            if len(distinct) == 2  # noqa: PLR2004 - binaire : pas de winsorisation
            else (
                float(np.quantile(filled, 1 - spec.clip_quantile)),
                float(np.quantile(filled, spec.clip_quantile)),
            )
        )
        filled = np.clip(filled, lo, hi)
        std = float(filled.std())
        if std < _MIN_STD:
            dropped.append(col)
            continue
        medians[col] = median
        bounds[col] = (lo, hi)
        # Binaires laissées en 0/1 : coefficient = log-HR directement lisible.
        continuous = spec.standardize and len(distinct) > 2  # noqa: PLR2004
        means[col] = float(filled.mean()) if continuous else 0.0
        stds[col] = std if continuous else 1.0
        if col in spline_df and len(np.unique(filled)) <= spline_df[col] + 1:
            linearised.append(col)
    levels: dict[str, tuple[str, ...]] = {}
    for col in cats.columns:
        level_counts = cats[col].fill_null("unknown").value_counts(sort=True)
        values = tuple(str(v) for v in level_counts[col].to_list())
        if len(values) < 2:  # noqa: PLR2004 - une catégorie = terme constant
            dropped.append(col)
            continue
        levels[col] = tuple(sorted(values))
    return {
        "dropped": tuple(dropped),
        "linearised": tuple(linearised),
        "medians": medians,
        "bounds": bounds,
        "means": means,
        "stds": stds,
        "levels": levels,
    }


def _interaction_columns(
    spec: DesignSpec, kept_num: set[str], levels: dict[str, tuple[str, ...]]
) -> list[tuple[str, str, str, str]]:
    """(name, group_col, level, x) for each non-reference level of each kept interaction.

    Built by hand rather than `C(g):x`: patsy would code one slope per level (full rank),
    collinear with the linear part of `cr(x)`. The reference level (first sorted) is omitted.
    """
    out = []
    for group, x in spec.interactions:
        if group in levels and x in kept_num:
            for level in levels[group][1:]:
                safe = "".join(ch if ch.isalnum() else "_" for ch in level)
                out.append((f"{x}__x__{group}_{safe}", group, level, x))
    return out


def _formula(
    spec: DesignSpec,
    kept_num: set[str],
    levels: dict[str, tuple[str, ...]],
    linear: set[str],
) -> str:
    terms = [f"C({c})" for c in spec.categorical if c in levels]
    for col, k in spec.splines:
        if col in kept_num:
            terms.append(col if col in linear else f"cr({col}, df={k}, constraints='center')")
    terms += [c for c in spec.linear if c in kept_num]
    terms += [name for name, *_ in _interaction_columns(spec, kept_num, levels)]
    return " + ".join(terms) if terms else "1"


def _offset(df: pl.DataFrame, spec: DesignSpec) -> np.ndarray:
    minutes = df.get_column(spec.exposure).cast(pl.Float64).to_numpy()
    if not np.isfinite(minutes).all() or (minutes <= 0).any():
        raise ValueError(
            f"{spec.exposure} invalide (null, NaN ou <= 0) : l'offset log(minutes/80) exige une"
            " exposition positive. Le runner exclut les lignes jouées sans minutes."
        )
    return np.asarray(np.log(minutes / EXPOSURE_REF_MINUTES), dtype=float)


def build_design(
    df: pl.DataFrame, spec: DesignSpec, fitted: FittedTransform | None = None
) -> Design:
    """Design matrix + offset (+ target if present). `fitted=None` means: learn on `df`."""
    validate_spec(spec)
    num = _numeric_frame(df, spec)
    cats = df.select([pl.col(c).cast(pl.String) for c in spec.categorical])
    if fitted is None:
        learned = _learn(num, cats, spec)
        formula = _formula(
            spec, set(learned["medians"]), learned["levels"], set(learned["linearised"])
        )
    else:
        learned = {
            "dropped": fitted.dropped,
            "linearised": fitted.linearised,
            "medians": fitted.medians,
            "bounds": fitted.bounds,
            "means": fitted.means,
            "stds": fitted.stds,
            "levels": fitted.levels,
        }
        formula = fitted.formula
    data: dict[str, Any] = {}
    for col, median in learned["medians"].items():
        values = np.clip(
            num[col].fill_null(median).to_numpy().astype(float), *learned["bounds"][col]
        )
        data[col] = (values - learned["means"][col]) / learned["stds"][col]
    for col, lv in learned["levels"].items():
        # Modalité absente du train -> modalité la plus fréquente du train (documenté).
        raw = cats[col].fill_null("unknown").to_list()
        fallback = lv[0]
        data[col] = pd.Categorical([v if v in lv else fallback for v in raw], categories=lv)
    for name, group, level, x in _interaction_columns(
        spec, set(learned["medians"]), learned["levels"]
    ):
        data[name] = data[x] * (np.asarray(data[group]) == level)
    frame = pd.DataFrame(data, index=pd.RangeIndex(len(df)))
    if fitted is None:
        matrix = patsy.dmatrix(formula, frame, NA_action="raise", return_type="dataframe")
        design_info = matrix.design_info
    else:
        design_info = fitted.design_info
        (matrix,) = patsy.build_design_matrices(
            [design_info], frame, NA_action="raise", return_type="dataframe"
        )
    transform = FittedTransform(
        formula=formula,
        dropped=tuple(learned["dropped"]),
        linearised=tuple(learned["linearised"]),
        medians=dict(learned["medians"]),
        bounds=dict(learned["bounds"]),
        means=dict(learned["means"]),
        stds=dict(learned["stds"]),
        levels=dict(learned["levels"]),
        design_info=design_info,
    )
    y = (
        df.get_column(spec.target).cast(pl.Float64).to_numpy()
        if spec.target in df.columns
        else None
    )
    return Design(
        X=np.asarray(matrix, dtype=float),
        columns=tuple(str(c) for c in matrix.columns),
        offset=_offset(df, spec),
        y=y,
        transform=transform,
    )
