"""Probabilistic classification metrics (docs/06 §3.2). All take played rows only."""

from dataclasses import dataclass, field

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

AUC_LEAK_ALERT = 0.75
CALIBRATION_SLOPE_RANGE = (0.8, 1.2)


@dataclass(frozen=True)
class Metrics:
    """Metric bundle for one set of predictions."""

    n: int
    prevalence: float
    log_loss: float
    brier: float
    brier_skill: float | None  # None when no reference predictions given
    auc_pr: float
    auc_roc: float
    calibration_slope: float
    calibration_intercept: float
    predicted_incidence: float
    alerts: tuple[str, ...] = field(default=())

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "n": self.n,
            "prevalence": self.prevalence,
            "log_loss": self.log_loss,
            "brier": self.brier,
            "brier_skill": self.brier_skill,
            "auc_pr": self.auc_pr,
            "auc_roc": self.auc_roc,
            "calibration_slope": self.calibration_slope,
            "calibration_intercept": self.calibration_intercept,
            "predicted_incidence": self.predicted_incidence,
        }


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def calibration(y: np.ndarray, logit_p: np.ndarray) -> tuple[float, float]:
    """Slope and intercept of the logistic regression of y on logit(p̂)."""
    if len(np.unique(y)) < 2 or np.std(logit_p) == 0:  # noqa: PLR2004
        return 0.0, float(np.mean(y))
    fit = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=200).fit(logit_p.reshape(-1, 1), y)
    return float(fit.coef_[0][0]), float(fit.intercept_[0])


def evaluate(y: np.ndarray, p: np.ndarray, p_reference: np.ndarray | None = None) -> Metrics:
    """Full metric bundle. `p` clipped away from 0/1 for log-loss stability."""
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    eps = 1e-6
    both_classes = len(np.unique(y)) == 2  # noqa: PLR2004
    with np.errstate(divide="ignore"):
        logit_p = np.log(p / (1 - p))
    brier_ref = (
        brier_score_loss(y, np.clip(p_reference, eps, 1 - eps)) if p_reference is not None else None
    )
    alerts: list[str] = []
    auc_roc = float(roc_auc_score(y, p)) if both_classes else float("nan")
    if both_classes and auc_roc > AUC_LEAK_ALERT:
        alerts.append(f"auc_roc>{AUC_LEAK_ALERT}: fuite probable ou labels dérivés")
    slope, intercept = calibration(y, logit_p)
    if both_classes and not CALIBRATION_SLOPE_RANGE[0] <= slope <= CALIBRATION_SLOPE_RANGE[1]:
        alerts.append(f"pente_calibration={slope:.2f} hors [0.8; 1.2]")
    # log_loss sklearn exige les deux classes dans y : labels fixes sinon.
    ll = float(log_loss(y, p, labels=[0, 1])) if not both_classes else float(log_loss(y, p))
    return Metrics(
        n=len(y),
        prevalence=float(y.mean()),
        log_loss=ll,
        brier=float(brier_score_loss(y, p)),
        brier_skill=(
            _safe_div(brier_ref - float(brier_score_loss(y, p)), brier_ref)
            if brier_ref is not None
            else None
        ),
        auc_pr=float(average_precision_score(y, p)) if y.sum() else float("nan"),
        auc_roc=auc_roc,
        calibration_slope=slope,
        calibration_intercept=intercept,
        predicted_incidence=float(p.mean()),
        alerts=tuple(alerts),
    )


def calibration_curve(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> dict[str, np.ndarray]:
    """Quantile-bin calibration curve: mean predicted vs observed per bin."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    bin_idx = np.digitize(p, edges[1:-1])
    return {
        "bin": np.array([i for i in range(n_bins) if (bin_idx == i).any()]),
        "p_pred": np.array([p[bin_idx == i].mean() for i in range(n_bins) if (bin_idx == i).any()]),
        "p_obs": np.array([y[bin_idx == i].mean() for i in range(n_bins) if (bin_idx == i).any()]),
        "n": np.array([int((bin_idx == i).sum()) for i in range(n_bins) if (bin_idx == i).any()]),
    }
