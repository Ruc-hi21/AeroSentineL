"""XGBoost 4-band failure-risk model.

Band codes follow severity: 0 NORMAL, 1 AT_RISK, 2 HIGH_RISK, 3 FAILURE_LIKELY.

The band probabilities are an ensemble of two XGBoost views of the same engine:
  * a direct multi-class classifier, and
  * the RUL regressor, turned into band probabilities by placing a Gaussian (sd = sigma cycles)
    around its prediction and integrating it over each band's RUL range.
p = (1 - blend) * p_classifier + blend * p_regressor. blend = 0 is the plain classifier.
"""

import numpy as np
from scipy.stats import norm
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from src.config import RISK_BANDS, RISK_BLEND_SIGMA, RISK_LIMITS, RUL_CAP, SEED


def rul_to_band(rul):
    """Map RUL values to band codes. Every RUL >= 0 lands in exactly one band."""
    rul = np.asarray(rul)
    codes = np.zeros(len(rul), dtype=int)  # NORMAL
    for code in range(1, len(RISK_BANDS)):  # later (more severe) bands overwrite earlier ones
        codes[rul <= RISK_LIMITS[RISK_BANDS[code]]] = code
    return codes


def rul_band_proba(rul, sigma=RISK_BLEND_SIGMA):
    """(n, 4) band probabilities from RUL point predictions with Gaussian uncertainty."""
    # Upper RUL edge of each band, most lenient first; +0.5 because RUL is counted in whole cycles.
    edges = np.array([np.inf] + [RISK_LIMITS[b] + 0.5 for b in RISK_BANDS[1:]] + [-np.inf])
    cdf = norm.cdf((edges[None, :] - np.asarray(rul, dtype=float)[:, None]) / sigma)
    return cdf[:, :-1] - cdf[:, 1:]


class FailureRiskClassifier:
    def __init__(self, params=None, blend=0.0, sigma=RISK_BLEND_SIGMA):
        self.params = params or {}
        self.blend = blend
        self.sigma = sigma
        self.rul_model = None  # an XGBRegressor predicting RUL, used when blend > 0
        self.model = XGBClassifier(
            tree_method="hist", n_jobs=-1, random_state=SEED,
            objective="multi:softprob",  # produces full probability distribution over classes
            **self.params,
        )

    def fit(self, X, bands, rul_model=None):
        # Square-root balanced weights: the rare severe bands still count more, at a smaller cost in
        # overall accuracy than fully balanced weights (compared in GroupKFold CV on FD001).
        self.model.fit(X, bands, sample_weight=np.sqrt(compute_sample_weight("balanced", bands)))
        self.rul_model = rul_model
        return self

    def predict_proba(self, X):
        """Returns class probability matrix (n_samples, 4)."""
        proba = self.model.predict_proba(X)
        if self.blend and self.rul_model is not None:
            rul = np.clip(self.rul_model.predict(X), 0, RUL_CAP)
            proba = (1 - self.blend) * proba + self.blend * rul_band_proba(rul, self.sigma)
        return proba

    def classify_band(self, X):
        """Return (band codes, probability of the chosen band)."""
        proba = self.predict_proba(X)
        codes = proba.argmax(axis=1)
        return codes, proba[np.arange(len(codes)), codes]
