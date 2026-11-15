"""Cluster bootstrap by player (docs/06 §3.2): resample player_keys, keep all their rows."""

from collections.abc import Callable

import numpy as np

DEFAULT_REPLICATIONS = 500


def cluster_bootstrap(
    player_keys: np.ndarray,
    score_fn: Callable[[np.ndarray], float],
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = 0,
) -> np.ndarray:
    """Bootstrap distribution of `score_fn(row_mask)` resampling whole players.

    `score_fn` receives a boolean row mask (all rows of the resampled players) and returns
    a scalar. Players with more rows weigh more, which is the intended exposure weighting.
    """
    keys = np.unique(player_keys)
    index_of = {k: i for i, k in enumerate(keys)}
    row_clusters = np.array([index_of[k] for k in player_keys])
    rng = np.random.default_rng(seed)
    scores = np.empty(replications)
    for r in range(replications):
        sampled = rng.choice(len(keys), size=len(keys), replace=True)
        mask = np.isin(row_clusters, sampled)
        scores[r] = score_fn(mask)
    return scores


def percentile_interval(scores: np.ndarray, level: float = 0.90) -> tuple[float, float]:
    """Central percentile interval (default 90 %)."""
    lo = (1 - level) / 2 * 100
    hi = (1 + level) / 2 * 100
    return float(np.percentile(scores, lo)), float(np.percentile(scores, hi))
