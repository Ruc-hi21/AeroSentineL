"""SHAP explanations, summed per sensor so results read as 'which sensors drove this'.

SHAP shows correlation with the prediction, not proof of a root cause.
"""

import numpy as np
import pandas as pd
import shap

from src.config import TOP_K_FACTORS
from src.features.engineering import sensor_of


class Explainer:
    def __init__(self, model):
        self.tree = shap.TreeExplainer(model)

    def sensor_contributions(self, X, class_index=None):
        """SHAP values per row, grouped by sensor. For a classifier pass the class per row."""
        values = np.asarray(self.tree.shap_values(X))
        if values.ndim == 3:  # multi-class: (rows, features, classes)
            values = values[np.arange(len(X)), :, class_index]
        per_feature = pd.DataFrame(values, columns=X.columns, index=X.index)
        return per_feature.T.groupby(sensor_of).sum().T

    def explain(self, X, class_index=None, top_k=TOP_K_FACTORS):
        """Top-k sensors per row as [{'sensor': ..., 'impact': ...}], largest |impact| first."""
        contributions = self.sensor_contributions(X, class_index)
        results = []
        for _, row in contributions.iterrows():
            top = row.abs().sort_values(ascending=False).index[:top_k]
            results.append([{"sensor": s, "impact": round(float(row[s]), 3)} for s in top])
        return results
