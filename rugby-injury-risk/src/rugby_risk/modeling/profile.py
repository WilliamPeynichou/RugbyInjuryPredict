"""Position load-profile simulator (F30): risk at each chained match, with 90 % credible bands.

The study stays by position. A "profile" is a set of load values typed by the user (position,
minutes per match, matches in the last 365 days, minutes in the last 28 days, international
window): it never carries a name or an identifier, and the player / team-season effects of the
model are integrated as for any new player (F22). Every output carries `WARNING`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import numpy as np
import polars as pl

from rugby_risk.modeling.curves import CURVE_VARIABLE, scenario_frame
from rugby_risk.modeling.hierarchical import CI_LEVEL, HierarchicalHazardModel

MAX_HORIZON: Final = 15
DEFAULT_DAYS_REST: Final = 7.0
_Q_LOW: Final = (1.0 - CI_LEVEL) / 2.0
_Q_HIGH: Final = 1.0 - _Q_LOW

WARNING: Final = (
    "**Avertissement** — Estimation statistique pour un *profil de charge par poste*, pas un "
    "pronostic individuel : le modèle ne connaît pas le joueur (effets joueur et équipe "
    "intégrés). Association, non causale. Cible : blessures entraînant au moins 2 matchs "
    "d'absence, reconstruites depuis des sources publiques (sous-déclaration des blessures "
    "courtes). Intervalles crédibles à 90 %, à lire avant la valeur centrale. Charge sur 28 "
    "jours figée sur l'horizon. Ne pas utiliser pour une décision médicale, de sélection ou "
    "contractuelle."
)
NOT_PROMOTED: Final = (
    "**Modèle non promu** : les critères de docs/06 §6 ne sont pas validés par une décision "
    "humaine (voir `reports/model_review_*.md`). Résultats exploratoires."
)


class ProfileError(ValueError):
    """Invalid profile or unusable model."""


@dataclass(frozen=True)
class PositionProfile:
    """Load profile typed by the user. No identifier field, by design (docs/07 §4)."""

    position_code: str
    minutes_per_match: float = 80.0
    apps_20min_365d: float | None = None
    min_28d: float | None = None
    intl_window: bool = False
    days_since_last_match: float = DEFAULT_DAYS_REST
    start_consecutive: int = 0
    horizon: int = 6

    def validate(self) -> None:
        if not 1 <= self.horizon <= MAX_HORIZON:
            raise ProfileError(f"horizon hors [1; {MAX_HORIZON}] : {self.horizon}")
        if not 0 < self.minutes_per_match <= 80:  # noqa: PLR2004 - durée d'un match
            raise ProfileError(f"minutes par match hors ]0; 80] : {self.minutes_per_match}")
        if self.start_consecutive < 0:
            raise ProfileError("start_consecutive négatif")
        for name in ("apps_20min_365d", "min_28d"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ProfileError(f"{name} négatif : {value}")


@dataclass(frozen=True)
class Band:
    mean: float
    low: float
    high: float


@dataclass(frozen=True)
class ProfileResult:
    profile: PositionProfile
    ns: tuple[int, ...]
    per_match: tuple[Band, ...]
    cumulative: tuple[Band, ...]
    factor: Band | None  # facteur multiplicatif moyen par match enchaîné
    extrapolated: tuple[int, ...]  # N au-delà du P99 du train (plafonnés par le design)


def _band(values: np.ndarray) -> Band:
    low, high = np.quantile(values, [_Q_LOW, _Q_HIGH])
    return Band(mean=float(values.mean()), low=float(low), high=float(high))


def profile_frame(model: HierarchicalHazardModel, profile: PositionProfile) -> pl.DataFrame:
    """One row per chained match: N = start .. start + horizon - 1, other features fixed."""
    profile.validate()
    if profile.position_code not in model.profiles_:
        raise ProfileError(
            f"Poste inconnu : {profile.position_code} (connus : {sorted(model.profiles_)})"
        )
    overrides: dict[str, Any] = {
        "intl_window": profile.intl_window,
        "days_since_last_match": profile.days_since_last_match,
    }
    if profile.apps_20min_365d is not None:
        overrides["apps_20min_365d"] = profile.apps_20min_365d
    if profile.min_28d is not None:
        overrides["min_28d"] = profile.min_28d
    ns = range(profile.start_consecutive, profile.start_consecutive + profile.horizon)
    return scenario_frame(
        model.profiles_[profile.position_code],
        overrides,
        ns,
        profile.minutes_per_match,
        profile.position_code,
    )


def simulate(model: HierarchicalHazardModel, profile: PositionProfile) -> ProfileResult:
    """Posterior risk per chained match, cumulative risk and per-match factor (per draw)."""
    if model.status != "ok":
        raise ProfileError(f"MCMC du modèle en échec ou absent (statut {model.status})")
    frame = profile_frame(model, profile)
    draws = model.predict_draws(frame)  # (tirages, horizon)
    cumulative = 1.0 - np.cumprod(1.0 - draws, axis=1)
    factor = None
    if draws.shape[1] > 1:
        ratios = np.log(draws[:, 1:] / draws[:, :-1]).mean(axis=1)
        factor = _band(np.exp(ratios))
    ns = tuple(int(n) for n in frame[CURVE_VARIABLE].to_list())
    bounds = model.transform_.bounds.get(CURVE_VARIABLE) if model.transform_ else None
    upper = bounds[1] if bounds else float("inf")
    return ProfileResult(
        profile=profile,
        ns=ns,
        per_match=tuple(_band(draws[:, k]) for k in range(draws.shape[1])),
        cumulative=tuple(_band(cumulative[:, k]) for k in range(draws.shape[1])),
        factor=factor,
        extrapolated=tuple(n for n in ns if n > upper),
    )


def _pct(b: Band) -> str:
    return f"{100 * b.mean:.1f} % [{100 * b.low:.1f} ; {100 * b.high:.1f}]"


def profile_markdown(
    result: ProfileResult,
    model: HierarchicalHazardModel,
    meta: dict[str, Any],
    *,
    promoted: bool,
) -> str:
    p = result.profile
    base = model.profiles_[p.position_code]

    def shown(value: float | None, key: str) -> str:
        if value is not None:
            return f"{value:g}"
        median = base.get(key)
        return f"{median:g} (médiane du poste)" if isinstance(median, float | int) else "—"

    lines = [
        f"# Profil de charge — poste {p.position_code}",
        "",
        WARNING,
        "",
        *([] if promoted else [NOT_PROMOTED, ""]),
        "## Profil saisi",
        "",
        "| Variable | Valeur |",
        "|---|---|",
        f"| Minutes par match | {p.minutes_per_match:g} |",
        f"| Matchs ≥ 20 min sur 365 j (club + sélection) | {shown(p.apps_20min_365d, 'apps_20min_365d')} |",  # noqa: E501
        f"| Minutes sur 28 j | {shown(p.min_28d, 'min_28d')} |",
        f"| Fenêtre internationale | {'oui' if p.intl_window else 'non'} |",
        f"| Jours de repos entre matchs | {p.days_since_last_match:g} |",
        f"| Matchs consécutifs déjà joués | {p.start_consecutive} |",
        "",
        "## Risque par match enchaîné (moyenne postérieure [IC90 crédible])",
        "",
        "| Match | N consécutifs avant | Risque du match | Risque cumulé |",
        "|---|---|---|---|",
    ]
    for k, (n, h, c) in enumerate(
        zip(result.ns, result.per_match, result.cumulative, strict=True), start=1
    ):
        flag = " ⚠ extrapolé" if n in result.extrapolated else ""
        lines.append(f"| {k} | {n}{flag} | {_pct(h)} | {_pct(c)} |")
    if result.factor is not None:
        f = result.factor
        lines += [
            "",
            f"Facteur multiplicatif moyen par match enchaîné : {f.mean:.3f} "
            f"[{f.low:.3f} ; {f.high:.3f}]. Un intervalle contenant 1 signifie qu'aucun effet "
            "de l'enchaînement n'est établi par les données.",
        ]
    if result.extrapolated:
        lines += [
            "",
            "⚠ N au-delà du 99e centile du train : la valeur est plafonnée par le design, le "
            "risque n'y augmente plus.",
        ]
    lines += [
        "",
        "## Provenance",
        "",
        f"- Artefact : `{meta.get('run_id')}` ({'promu' if promoted else 'non promu'})",
        f"- dataset_version : `{meta.get('dataset_version')}`",
        f"- Saisons d'estimation : {', '.join(meta.get('seasons', []))}",
        f"- git_sha : `{meta.get('git_sha')}`",
    ]
    return "\n".join(lines) + "\n"
