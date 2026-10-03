"""XGBoost RUL regressor with an 80% prediction interval."""

import numpy as np
from xgboost import XGBRegressor

from src.config import RUL_CAP, RUL_INTERVAL, SEED

BASE_PARAMS = {"tree_method": "hist", "n_jobs": -1, "random_state": SEED}
# Shallow, regularised trees: deeper quantile models overfit and their intervals came out
# too narrow (69% validation coverage for a nominal 80% interval vs. 87% with these).
INTERVAL_PARAMS = {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05,
                   "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 20}


class RULRegressor:
    def __init__(self, params=None):
        self.params = params or {}
        self.model = XGBRegressor(**BASE_PARAMS, **self.params)
        self.interval_model = XGBRegressor(
            **BASE_PARAMS, **INTERVAL_PARAMS,
            objective="reg:quantileerror", quantile_alpha=np.array(RUL_INTERVAL),
        )

    def fit(self, X, y):
        self.model.fit(X, y)
        self.interval_model.fit(X, y)
        return self

    def predict(self, X):
        return np.clip(self.model.predict(X), 0, RUL_CAP)

    def predict_interval(self, X):
        """(low, high) bounds, widened if needed so they always contain the point prediction."""
        bounds = np.clip(self.interval_model.predict(X), 0, RUL_CAP)
        point = self.predict(X)
        low = np.minimum.reduce([bounds[:, 0], bounds[:, 1], point])
        high = np.maximum.reduce([bounds[:, 0], bounds[:, 1], point])
        return low, high
