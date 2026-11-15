"""F16: annotation metrics — precision, recall by confidence band, isotone recalibration."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BANDS = ((0.0, 0.6), (0.6, 0.9), (0.9, 1.01))
MIN_POOLS = 2
DECISIONS = ("injury", "not_injury", "unsure")


@dataclass
class Metrics:
    n_labeled: int
    n_injury: int
    n_not_injury: int
    precision: float
    recall: float
    precision_by_band: list[tuple[str, int, float | None]]


def load_annotations(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [
            row for row in csv.DictReader(fh) if row.get("decision") in ("injury", "not_injury")
        ]


def compute_metrics(rows: list[dict[str, Any]]) -> Metrics:
    """rows : episode_kind, source_confidence, decision (injury | not_injury)."""
    labeled = [r for r in rows if str(r["decision"]) in ("injury", "not_injury")]
    episodes = [r for r in labeled if r["episode_kind"] == "episode"]
    non_episodes = [r for r in labeled if r["episode_kind"] == "non_episode"]
    tp = sum(1 for r in episodes if r["decision"] == "injury")
    fp = len(episodes) - tp
    fn = sum(1 for r in non_episodes if r["decision"] == "injury")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    bands = []
    for lo, hi in BANDS:
        sel = [r for r in episodes if lo <= float(str(r["source_confidence"])) < hi]
        t = sum(1 for r in sel if r["decision"] == "injury")
        bands.append((f"[{lo:.1f}, {hi:.1f})", len(sel), t / len(sel) if sel else None))
    return Metrics(
        n_labeled=len(labeled),
        n_injury=tp + fn,
        n_not_injury=fp + len(non_episodes) - fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        precision_by_band=bands,
    )


def isotonic_recalibration(
    pairs: list[tuple[float, int]],
) -> list[tuple[float, float]]:
    """PAV isotonic fit on (confidence, observed) — pour recalibrer les scores."""
    ordered = sorted(pairs)
    levels: list[list[float]] = []  # pools PAV : [valeur, poids, premier index]
    for i, (_conf, obs) in enumerate(ordered):
        levels.append([float(obs), 1.0, float(i)])
        while len(levels) >= MIN_POOLS and levels[-2][0] > levels[-1][0]:
            hi = levels.pop()
            lo = levels.pop()
            weight = lo[1] + hi[1]
            levels.append([(lo[0] * lo[1] + hi[0] * hi[1]) / weight, weight, lo[2]])
    calibrated = []
    for i, (conf, _obs) in enumerate(ordered):
        level = next(lv for lv in levels if lv[2] <= i)
        calibrated.append((conf, level[0]))
    return calibrated


def quality_report_markdown(rows: list[dict[str, Any]], metrics: Metrics) -> str:
    lines = [
        "# Qualité des étiquettes de blessure (F16)",
        "",
        f"- Épisodes annotés : {metrics.n_labeled}",
        f"- Précision (échantillon) : {metrics.precision:.2%}",
        f"- Rappel (échantillon) : {metrics.recall:.2%}",
        "",
        "## Précision par bande de confiance",
        "",
        "| Bande | n | Précision |",
        "|---|---|---|",
    ]
    for band, n, prec in metrics.precision_by_band:
        lines.append(
            f"| {band} | {n} | {prec:.2%} |" if prec is not None else f"| {band} | {n} | — |"
        )
    lines += [
        "",
        "Critère d'acceptation : précision >= 0,85 sur les épisodes de confiance >= 0,6"
        " après annotation humaine (hors périmètre de l'agent).",
    ]
    return "\n".join(lines) + "\n"
