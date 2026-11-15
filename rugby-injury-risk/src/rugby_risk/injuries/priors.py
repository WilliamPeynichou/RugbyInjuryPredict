"""F16 prior control: reconstructed incidence vs docs/02 priors (40-110 / 1000 h)."""

from dataclasses import dataclass
from typing import Any

PRIOR_RANGE = (40.0, 110.0)  # blessures en match / 1000 h, docs/02-science-priors.md §2


@dataclass
class IncidenceRow:
    season: str
    position_group: str
    injuries: int
    hours: float
    per_1000h: float | None


def incidence_rows(con: Any, min_confidence: float | None = None) -> list[IncidenceRow]:
    """In-match injuries (context='match') per season x position group, over match hours.

    `min_confidence` restricts to the episodes kept as ML label (`y_injury`, F17): without it
    the control measures detection, not the target actually modelled.
    """
    conf_filter = "" if min_confidence is None else "and e.source_confidence >= ?"
    injuries = con.execute(
        f"""select m.season_id, coalesce(p.position_group, 'unknown') as pg, count(*) as n
           from fact_injury_event e
           join fact_match m on m.match_id = e.onset_match_id
           left join dim_player p on p.player_id = e.player_id
           where e.context = 'match' {conf_filter}
           group by 1, 2 order by 1, 2""",
        [] if min_confidence is None else [min_confidence],
    ).fetchall()
    hours = con.execute(
        """select m.season_id, coalesce(p.position_group, 'unknown') as pg,
                  sum(a.minutes_played) / 60.0 as hours
           from fact_appearance a
           join fact_match m on m.match_id = a.match_id
           left join dim_player p on p.player_id = a.player_id
           where a.minutes_played is not null
           group by 1, 2 order by 1, 2"""
    ).fetchall()
    hour_of = {(s, g): float(h) for s, g, h in hours}
    return [
        IncidenceRow(
            season=str(s),
            position_group=str(g),
            injuries=int(n),
            hours=hour_of.get((s, g), 0.0),
            per_1000h=(int(n) / hour_of[(s, g)] * 1000.0) if hour_of.get((s, g)) else None,
        )
        for s, g, n in injuries
    ]


def prior_violations(rows: list[IncidenceRow]) -> list[IncidenceRow]:
    return [
        r
        for r in rows
        if r.per_1000h is not None and not PRIOR_RANGE[0] <= r.per_1000h <= PRIOR_RANGE[1]
    ]


def _table(rows: list[IncidenceRow]) -> list[str]:
    lines = [
        "| Saison | Groupe de poste | Blessures | Heures | /1000 h |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        rate = f"{r.per_1000h:.1f}" if r.per_1000h is not None else "—"
        lines.append(f"| {r.season} | {r.position_group} | {r.injuries} | {r.hours:.0f} | {rate} |")
    return lines


def pooled_rate(rows: list[IncidenceRow]) -> float | None:
    """Pooled rate / 1000 h over all cells (hours counted once per season x group)."""
    hours = {(r.season, r.position_group): r.hours for r in rows}
    total_h = sum(hours.values())
    return sum(r.injuries for r in rows) / total_h * 1000.0 if total_h else None


def _fmt(rate: float | None) -> str:
    return "—" if rate is None else f"{rate:.1f}"


def incidence_markdown(
    rows: list[IncidenceRow],
    label_rows: list[IncidenceRow] | None = None,
    label_threshold: float | None = None,
) -> str:
    """Report: all detected match injuries (prior check), then the ML label subset if given."""
    lines = [
        "# Incidence reconstruite vs priors (docs/02 §2)",
        "",
        f"Plage attendue : {PRIOR_RANGE[0]:.0f}-{PRIOR_RANGE[1]:.0f} blessures en match / 1000 h.",
        "",
        "## Toutes les blessures en match détectées (contrôle de détection)",
        "",
        *_table(rows),
    ]
    outside = prior_violations(rows)
    lines += [
        "",
        f"Cellules hors plage : {len(outside)}" + ("" if not outside else " (asset check WARN)"),
    ]
    if label_rows is not None:
        lines += [
            "",
            f"## Label ML `y_injury` (confiance >= {label_threshold})",
            "",
            "Cible réellement modélisée (F17-F22). Les sorties précoces sans absence ultérieure",
            "(score « sortie seule » sous le seuil) en sont exclues : la cible sous-déclare les",
            "blessures courtes par construction. Résultats conditionnels à cette définition.",
            "",
            *_table(label_rows),
            "",
            f"Incidence poolée : toutes = {_fmt(pooled_rate(rows))} / 1000 h ; "
            f"label ML = {_fmt(pooled_rate(label_rows))} / 1000 h.",
        ]
    return "\n".join(lines) + "\n"
