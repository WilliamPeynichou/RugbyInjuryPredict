"""F16: fuse exit / absence / announcement signals into injury episode candidates.

Pure functions over plain dicts; no warehouse access here (the Dagster asset feeds
the inputs). Grain docs/04 §3 : (player_id, onset_date, body_region), merged when
the gap is < merge_gap_days and the region matches (or is unknown).
"""

import json
from dataclasses import dataclass, field
from datetime import date

import polars as pl

from rugby_risk.injuries.rules import FusionRules

ONSET_EXIT, ONSET_ANNOUNCEMENT, ONSET_ABSENCE = "exit", "announcement", "absence"
CONTEXTS = ("match", "training", "unknown")
SEVERITY = ("minimal_mild", "moderate", "severe", "unknown")


@dataclass
class Signal:
    kind: str  # exit | announcement | absence
    player_id: int
    signal_date: date
    strength: float = 0.0  # signal_strength (exit) ; 1.0 (announcement/absence)
    match_id: int | None = None
    context: str = "unknown"
    body_region: str | None = None
    injury_type: str | None = None
    is_concussion: bool = False
    detailed: bool = False  # annonce avec zone ou durée précisée
    run_end: date | None = None  # absence: dernier match manqué
    return_date: date | None = None  # absence: premier match rejoué après la période
    censored_end: bool = False
    evidence: list[dict[str, object]] = field(default_factory=list)


@dataclass
class Episode:
    player_id: int
    onset_date: date
    onset_match_id: int | None
    context: str
    body_region: str | None
    injury_type: str | None
    is_concussion: bool
    return_date: date | None
    days_missed: int | None
    severity_class: str
    censored: bool
    source_confidence: float
    signals: list[str]
    evidence: list[dict[str, object]]


def score_episode(signals: list[Signal], rules: FusionRules) -> float:
    """Confidence from the combination table (config/injury_rules.yaml, section fusion)."""
    exit_strength = max((s.strength for s in signals if s.kind == ONSET_EXIT), default=0.0)
    has_exit = exit_strength > 0
    has_absence = any(s.kind == ONSET_ABSENCE for s in signals)
    announces = [s for s in signals if s.kind == ONSET_ANNOUNCEMENT]
    detailed = any(s.detailed for s in announces)
    if has_exit and has_absence and announces:
        base = rules.exit_absence_announcement
    elif has_exit and has_absence:
        base = rules.exit_absence
    elif has_exit and announces:
        base = rules.exit_announcement
    elif has_exit:
        base = exit_strength * rules.exit_weight
    elif has_absence and announces:
        base = rules.exit_absence
    elif has_absence:
        base = rules.absence_alone
    elif announces:
        base = min(
            rules.announcement_alone + (rules.announcement_detail_bonus if detailed else 0.0),
            rules.confidence_cap,
        )
    else:
        base = 0.0
    return round(min(base, rules.confidence_cap), 4)


DAYS_MILD_MAX = 7
DAYS_MODERATE_MAX = 28


def _severity(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days <= DAYS_MILD_MAX:
        return "minimal_mild"
    if days <= DAYS_MODERATE_MAX:
        return "moderate"
    return "severe"


def _episode(player_signals: list[Signal], rules: FusionRules) -> Episode:
    exits = [s for s in player_signals if s.kind == ONSET_EXIT]
    announces = [s for s in player_signals if s.kind == ONSET_ANNOUNCEMENT]
    absences = [s for s in player_signals if s.kind == ONSET_ABSENCE]
    exit_signal = max(exits, key=lambda s: s.strength, default=None)
    onset_date, onset_match, context = None, None, "unknown"
    if exit_signal is not None:
        onset_date, onset_match, context = exit_signal.signal_date, exit_signal.match_id, "match"
    elif announces:
        dated = [s for s in announces if s.signal_date is not None]
        if dated:
            onset_date = min(dated, key=lambda s: s.signal_date).signal_date
            context = next((s.context for s in dated if s.context in CONTEXTS), "unknown")
    if onset_date is None and absences:
        onset_date = min(s.signal_date for s in absences)
    if onset_date is None:  # ne devrait pas arriver : un signal a toujours une date
        onset_date = min(s.signal_date for s in player_signals)
    # retour : premier match rejoué après l'onset (renseigné par l'asset pour l'absence)
    returns = [s.return_date for s in player_signals if s.kind == ONSET_ABSENCE and s.return_date]
    return_date = min((d for d in returns if d > onset_date), default=None)
    days_missed = (return_date - onset_date).days if return_date else None
    best = max(announces, key=lambda s: (s.detailed, s.signal_date), default=None)
    censored = return_date is None or any(s.censored_end for s in absences)
    return Episode(
        player_id=player_signals[0].player_id,
        onset_date=onset_date,
        onset_match_id=onset_match,
        context=context,
        body_region=best.body_region if best else None,
        injury_type=best.injury_type if best else None,
        is_concussion=any(s.is_concussion for s in announces),
        return_date=return_date,
        days_missed=days_missed,
        severity_class=_severity(days_missed),
        censored=censored,
        source_confidence=score_episode(player_signals, rules),
        signals=sorted({s.kind for s in player_signals}),
        evidence=[e for s in player_signals for e in s.evidence],
    )


def _mergeable(a: Episode, b: Episode, rules: FusionRules) -> bool:
    if a.player_id != b.player_id:
        return False
    regions = {r for r in (a.body_region, b.body_region) if r}
    if len(regions) > 1:
        return False
    end = a.return_date or a.onset_date
    gap = (b.onset_date - end).days
    return -rules.merge_gap_days < gap < rules.merge_gap_days


def _merge(a: Episode, b: Episode, rules: FusionRules) -> Episode:
    signals = [s for s in (a.signals + b.signals)]
    # re-scorer depuis les attributs conservés : on ne garde que le max (table ≥ composantes)
    merged = min((a, b), key=lambda e: e.onset_date)
    later = b if merged is a else a
    onset_match = merged.onset_match_id or later.onset_match_id
    return Episode(
        player_id=merged.player_id,
        onset_date=merged.onset_date,
        onset_match_id=onset_match,
        context=merged.context if merged.context == "match" else later.context,
        body_region=merged.body_region or later.body_region,
        injury_type=merged.injury_type or later.injury_type,
        is_concussion=merged.is_concussion or later.is_concussion,
        return_date=max((d for d in (merged.return_date, later.return_date) if d), default=None),
        days_missed=None,
        severity_class="unknown",
        censored=merged.censored and later.censored,
        source_confidence=max(merged.source_confidence, later.source_confidence),
        signals=sorted(set(signals)),
        evidence=merged.evidence + later.evidence,
    )


def fuse(
    signals: list[Signal], rules: FusionRules, opt_out: set[int] | None = None
) -> list[Episode]:
    """Group signals per player within `signal_window_days`, then merge close episodes."""
    blocked = opt_out or set()
    episodes: list[Episode] = []
    by_player: dict[int, list[Signal]] = {}
    for s in signals:
        if s.player_id not in blocked:
            by_player.setdefault(s.player_id, []).append(s)
    for _pid, player_signals in by_player.items():
        ordered = sorted(player_signals, key=lambda s: s.signal_date)
        groups: list[list[Signal]] = []
        for sig in ordered:
            if groups and (sig.signal_date - groups[-1][0].signal_date).days <= (
                rules.signal_window_days
            ):
                groups[-1].append(sig)
            else:
                groups.append([sig])
        episodes.extend(_episode(g, rules) for g in groups)
    merged: list[Episode] = []
    for ep in sorted(episodes, key=lambda e: (e.player_id, e.onset_date)):
        if merged and _mergeable(merged[-1], ep, rules):
            merged[-1] = _merge(merged[-1], ep, rules)
        else:
            merged.append(ep)
    for ep in merged:  # recalculer days/severity après fusion
        ep.days_missed = (ep.return_date - ep.onset_date).days if ep.return_date else None
        ep.severity_class = _severity(ep.days_missed)
    return merged


def episode_frame(episodes: list[Episode]) -> pl.DataFrame:
    """Staging frame `injury_episode` (source=fusion), schema-compatible with read_staging."""
    return pl.DataFrame(
        {
            "player_id": pl.Series([e.player_id for e in episodes], dtype=pl.Int64),
            "onset_date": pl.Series([e.onset_date for e in episodes], dtype=pl.Date),
            "onset_match_id": pl.Series([e.onset_match_id for e in episodes], dtype=pl.Int64),
            "context": pl.Series([e.context for e in episodes], dtype=pl.String),
            "body_region": pl.Series([e.body_region for e in episodes], dtype=pl.String),
            "injury_type": pl.Series([e.injury_type for e in episodes], dtype=pl.String),
            "is_concussion": pl.Series([e.is_concussion for e in episodes], dtype=pl.Boolean),
            "return_date": pl.Series([e.return_date for e in episodes], dtype=pl.Date),
            "days_missed": pl.Series([e.days_missed for e in episodes], dtype=pl.Int64),
            "severity_class": pl.Series([e.severity_class for e in episodes], dtype=pl.String),
            "censored": pl.Series([e.censored for e in episodes], dtype=pl.Boolean),
            "source_confidence": pl.Series(
                [e.source_confidence for e in episodes], dtype=pl.Float64
            ),
            "signals": pl.Series(["|".join(e.signals) for e in episodes], dtype=pl.String),
            "evidence": pl.Series(
                [json.dumps(e.evidence, ensure_ascii=False) for e in episodes],
                dtype=pl.String,
            ),
        }
    )
