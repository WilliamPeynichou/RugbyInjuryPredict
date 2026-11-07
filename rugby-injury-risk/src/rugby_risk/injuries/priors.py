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


def incidence_rows(con: Any) -> list[IncidenceRow]:
    """In-match injuries (context='match') per season x position group, over match hours."""
    injuries = con.execute(
        """select m.season_id, coalesce(p.position_group, 'unknown') as pg, count(*) as n
           from fact_injury_event e
           join fact_match m on m.match_id = e.onset_match_id
           left join dim_player p on p.player_id = e.player_id
           where e.context = 'match'
           group by 1, 2 order by 1, 2"""
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


def incidence_markdown(rows: list[IncidenceRow]) -> str:
    lines = [
        "# Incidence reconstruite vs priors (docs/02 §2)",
        "",
        f"Plage attendue : {PRIOR_RANGE[0]:.0f}-{PRIOR_RANGE[1]:.0f} blessures en match / 1000 h.",
        "",
        "| Saison | Groupe de poste | Blessures | Heures | /1000 h |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        rate = f"{r.per_1000h:.1f}" if r.per_1000h is not None else "—"
        lines.append(f"| {r.season} | {r.position_group} | {r.injuries} | {r.hours:.0f} | {rate} |")
    outside = prior_violations(rows)
    lines += [
        "",
        f"Cellules hors plage : {len(outside)}" + ("" if not outside else " (asset check WARN)"),
    ]
    return "\n".join(lines) + "\n"
