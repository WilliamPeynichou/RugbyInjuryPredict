"""ALE (Accumulated Local Effects) for one feature (F23, docs/06 §4).

Model-agnostic: only needs a predict function on a numpy design matrix. Unlike PDP, ALE
averages *local* differences within bins, so it stays correct when the feature correlates
with the others (e.g. `consecutive_matches` correlates with `min_28d`).
"""

from collections.abc import Callable
from typing import Final

import numpy as np

_MIN_BIN: Final = 5


def ale_1d(
    predict: Callable[[np.ndarray], np.ndarray],
    matrix: np.ndarray,
    j: int,
    *,
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Centers and ALE effects of feature `j`, mean-centred over the row distribution.

    Each bin contributes the mean prediction difference between replacing x_j by the bin
    upper edge and by the bin lower edge (local effect); effects accumulate left to right.
    """
    if matrix.ndim != 2:  # noqa: PLR2004 - matrice = (lignes, colonnes)
        raise ValueError("matrix doit être une matrice (lignes, colonnes)")
    x = np.asarray(matrix[:, j], dtype=float)
    order = np.argsort(x, kind="stable")
    edges = np.quantile(x[order], np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    bins = np.clip(np.searchsorted(edges[1:-1], x, side="right"), 0, n_bins - 1)

    diffs = np.zeros(n_bins)
    counts = np.zeros(n_bins)
    for b in range(n_bins):
        mask = bins == b
        n = int(mask.sum())
        if n < _MIN_BIN:
            continue
        hi = matrix[mask].copy()
        lo = matrix[mask].copy()
        hi[:, j] = edges[b + 1] if np.isfinite(edges[b + 1]) else x[order][-1]
        lo[:, j] = edges[b] if np.isfinite(edges[b]) else x[order][0]
        diffs[b] = float(np.mean(predict(hi) - predict(lo)))
        counts[b] = n
    effects = np.cumsum(diffs)
    mean = float(np.sum(effects * counts) / np.sum(counts)) if counts.sum() else 0.0
    centers = np.array([x[bins == b].mean() if counts[b] else np.nan for b in range(n_bins)])
    return centers, effects - mean
