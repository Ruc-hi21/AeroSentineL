"""XGBoost 4-band failure-risk classifier.

Band codes follow severity: 0 NORMAL, 1 AT_RISK, 2 HIGH_RISK, 3 FAILURE_LIKELY.
"""

import numpy as np
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from src.config import RISK_BANDS, RISK_LIMITS, SEED


def rul_to_band(rul):
    """Map RUL values to band codes. Every RUL >= 0 lands in exactly one band."""
    rul = np.asarray(rul)
    codes = np.zeros(len(rul), dtype=int)  # NORMAL
    for code in range(1, len(RISK_BANDS)):  # later (more severe) bands overwrite earlier ones
        codes[rul <= RISK_LIMITS[RISK_BANDS[code]]] = code
    return codes


class FailureRiskClassifier:
    def __init__(self, params=None):
        self.params = params or {}
        self.model = XGBClassifier(
            tree_method="hist", n_jobs=-1, random_state=SEED,
            objective="multi:softprob", **self.params,
        )

    def fit(self, X, bands):
        # Balanced weights so the rare severe bands are not ignored.
        self.model.fit(X, bands, sample_weight=compute_sample_weight("balanced", bands))
        return self

    def predict_proba(self, X):
        return self.model.predict_proba(X)

    def classify_band(self, X):
        """Return (band codes, probability of the chosen band)."""
        proba = self.predict_proba(X)
        codes = proba.argmax(axis=1)
        return codes, proba[np.arange(len(codes)), codes]
