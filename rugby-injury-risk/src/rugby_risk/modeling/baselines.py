"""Baselines M0 (F19) : taux de blessure par poste avec offset exposition.

Référence à battre pour tous les modèles (docs/06-modeling.md §2). Formulation
Poisson : lambda_p = blessures / heures d'exposition par `position_code`, lissage
gamma-Poisson empirique-bayésien vers le taux du `position_group` quand l'exposition
est faible. Prédiction par ligne jouée : P = 1 - exp(-lambda * minutes/60).
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl

from rugby_risk.modeling.priors import (
    CONCUSSION_TOP14_2014_18,
    HOOKER_PREMIERSHIP_2002_04,
    INCIDENCE_PREMIERSHIP_2022_23,
    rate_to_match_prob,
)

_MIN_RATE = 1e-8  # plancher de taux : garde log/exp numériquement stables


@dataclass
class _Rates:
    """Nested rate table: code -> rate, group -> rate, global rate (per hour)."""

    by_code: dict[str, float] = field(default_factory=dict)
    code_to_group: dict[str, str] = field(default_factory=dict)
    by_group: dict[str, float] = field(default_factory=dict)
    global_rate: float = 0.0  # 0.0 = exposition nulle (fit refuse de prédire)
    # Exposure stats for the report (per position_code).
    exposure: dict[str, tuple[float, float]] = field(default_factory=dict)  # hours, injuries


def _check_minutes(minutes: np.ndarray, context: str) -> None:
    if minutes.size == 0:
        return
    if not np.isfinite(minutes).all() or (minutes < 0).any():
        raise ValueError(
            f"minutes_played invalides ({context}) : NaN/négatives présentes."
            " Le runner exclut les lignes jouées sans exposition connue."
        )


def _fit_rates(
    df: pl.DataFrame,
    target_col: str,
    minutes_col: str,
    group_col: str | None,
    smoothing_hours: float,
) -> _Rates:
    """Gamma-Poisson shrinkage: rate = (injuries + a * rate_parent) / (hours + a)."""
    out = _Rates()
    if df.is_empty():
        return out
    minutes = df.get_column(minutes_col).to_numpy().astype(float)
    _check_minutes(minutes, "fit")
    y = df.get_column(target_col).to_numpy().astype(float)
    hours_total = float(minutes.sum() / 60.0)
    inj_total = float(y.sum())
    if hours_total <= 0 or inj_total < 0:
        return out
    out.global_rate = max(inj_total / hours_total, 1e-9)

    codes = (
        df.get_column("position_code").cast(pl.String).to_numpy()
        if "position_code" in df.columns
        else None
    )
    groups = (
        df.get_column(group_col).cast(pl.String).to_numpy()
        if group_col is not None and group_col in df.columns
        else None
    )

    def _level(key_values: np.ndarray | None) -> dict[str, tuple[float, float]]:
        """(hours, injuries) per key."""
        if key_values is None:
            return {}
        agg: dict[str, list[float]] = {}
        for k, m, t in zip(key_values, minutes, y, strict=True):
            agg.setdefault(k, [0.0, 0.0])
            agg[k][0] += float(m) / 60.0
            agg[k][1] += float(t)
        return {k: (v[0], v[1]) for k, v in agg.items()}

    base = _level(codes)
    if codes is None:
        return out

    # Taux brut par groupe = parent du lissage ; taux global en dernier recours.
    if groups is not None:
        for g, (g_hours, g_inj) in _level(groups).items():
            out.by_group[g] = (g_inj / g_hours) if g_hours > 0 else out.global_rate
        for c, g in zip(codes, groups, strict=True):
            out.code_to_group.setdefault(c, g)

    def _smoothed(hours: float, injuries: float, parent_rate: float) -> float:
        return (injuries + smoothing_hours * parent_rate) / (hours + smoothing_hours)

    for key, (hours, injuries) in base.items():
        parent_rate = out.by_group.get(out.code_to_group.get(key, ""), out.global_rate)
        out.by_code[key] = max(_smoothed(hours, injuries, parent_rate), _MIN_RATE)
        out.exposure[key] = (hours, injuries)
    return out


def _predict_from_rates(
    rates: _Rates, df: pl.DataFrame, minutes_col: str, group_col: str | None
) -> np.ndarray:
    minutes = df.get_column(minutes_col).to_numpy().astype(float)
    _check_minutes(minutes, "predict")
    n = len(df)
    lam = np.full(n, rates.global_rate, dtype=float)
    if "position_code" in df.columns and rates.by_code:
        codes = df.get_column("position_code").cast(pl.String).to_numpy()
        for i, c in enumerate(codes):
            lam[i] = rates.by_code.get(c, lam[i])
        if group_col is not None and group_col in df.columns and rates.by_group:
            groups = df.get_column(group_col).cast(pl.String).to_numpy()
            for i, c in enumerate(codes):
                if c not in rates.by_code:
                    lam[i] = rates.by_group.get(groups[i], rates.global_rate)
    hazard: np.ndarray = lam * minutes / 60.0
    return np.asarray(1.0 - np.exp(-hazard), dtype=float)


class GlobalRateModel:
    """M0 global : un seul taux lambda pour tous les joueurs."""

    name = "m0_global"

    def __init__(
        self,
        target_col: str = "y_injury",
        minutes_col: str = "minutes_played",
    ) -> None:
        self.target_col = target_col
        self.minutes_col = minutes_col
        self.rates_: _Rates | None = None

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "GlobalRateModel":
        del valid
        self.rates_ = _fit_rates(
            train, self.target_col, self.minutes_col, None, smoothing_hours=0.0
        )
        if self.rates_.global_rate <= _MIN_RATE:
            raise ValueError("Exposition nulle: impossible d'estimer le taux global")
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self.rates_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        return _predict_from_rates(self.rates_, df, self.minutes_col, None)

    def params(self) -> dict[str, Any]:
        rate = self.rates_.global_rate if self.rates_ else None
        return {"target_col": self.target_col, "rate_per_1000h": rate * 1000 if rate else None}

    def report_tables(self) -> dict[str, str]:
        if self.rates_ is None:
            return {}
        rate = self.rates_.global_rate * 1000
        return {
            "Taux M0 global": (
                "| Indicateur | Valeur |\n|---|---|\n"
                f"| Taux global (/1000 h) | {rate:.1f} |\n"
                f"| P(match 80 min) | {rate_to_match_prob(rate, 80):.4f} |\n"
                f"| P(match 50 min) | {rate_to_match_prob(rate, 50):.4f} |"
            )
        }


class PositionRateModel:
    """M0 par poste : taux par `position_code`, lissé vers le `position_group`.

    Le lissage gamma-Poisson stabilise les postes à faible exposition :
    rate_p = (blessures_p + a * rate_groupe) / (heures_p + a), avec `a` =
    `smoothing_hours` heures d'exposition virtuelle.
    """

    name = "m0_position"

    def __init__(
        self,
        target_col: str = "y_injury",
        minutes_col: str = "minutes_played",
        group_col: str = "position_group",
        smoothing_hours: float = 200.0,
    ) -> None:
        if smoothing_hours < 0:
            raise ValueError(f"smoothing_hours négatif: {smoothing_hours}")
        self.target_col = target_col
        self.minutes_col = minutes_col
        self.group_col = group_col
        self.smoothing_hours = smoothing_hours
        self.rates_: _Rates | None = None

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "PositionRateModel":
        del valid
        self.rates_ = _fit_rates(
            train, self.target_col, self.minutes_col, self.group_col, self.smoothing_hours
        )
        if self.rates_.global_rate <= _MIN_RATE:
            raise ValueError("Exposition nulle: impossible d'estimer les taux")
        return self

    def predict_proba(self, df: pl.DataFrame) -> np.ndarray:
        if self.rates_ is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba()")
        return _predict_from_rates(self.rates_, df, self.minutes_col, self.group_col)

    def params(self) -> dict[str, Any]:
        return {
            "target_col": self.target_col,
            "group_col": self.group_col,
            "smoothing_hours": self.smoothing_hours,
            "n_positions": len(self.rates_.by_code) if self.rates_ else 0,
        }

    def report_tables(self) -> dict[str, str]:
        """Taux par poste (/1000 h) avec IC Poisson exact, comparé aux priors."""
        if self.rates_ is None or not self.rates_.exposure:
            return {}
        from scipy.stats import gamma  # noqa: PLC0415 - dép déclarée, import paresseux

        lines = [
            "| Poste | Groupe | Heures | Blessures | Taux /1000 h | IC95 % | P(match 80 min) |",
            "|---|---|---|---|---|---|---|",
        ]
        for code in sorted(self.rates_.by_code):
            hours, injuries = self.rates_.exposure[code]
            rate = self.rates_.by_code[code] * 1000
            # IC exact Poisson (prior gamma de Jeffreys a=0.5) sur le comptage brut.
            if hours > 0:
                lo = gamma.ppf(0.025, 0.5 + injuries, scale=1.0) / hours * 1000
                hi = gamma.ppf(0.975, 0.5 + injuries, scale=1.0) / hours * 1000
            else:
                lo = hi = float("nan")
            group = self.rates_.code_to_group.get(code, "")
            lines.append(
                f"| {code} | {group} | {hours:.0f} | {injuries:.0f}"
                f" | {rate:.1f} | [{lo:.1f}; {hi:.1f}]"
                f" | {rate_to_match_prob(rate, 80):.4f} |"
            )
        refs = (
            "\n\nRéférences priors (/1000 h) :"
            f" Premiership 2022-23 = {INCIDENCE_PREMIERSHIP_2022_23:.0f},"
            f" talonneur Premiership 2002-04 = {HOOKER_PREMIERSHIP_2002_04:.0f},"
            f" commotion Top 14 2014-18 = {CONCUSSION_TOP14_2014_18:.1f}"
            " (ne couvre pas la sous-déclaration des données publiques)."
        )
        return {"Taux M0 par poste": "\n".join(lines) + refs}
