"""Component recognition: decide which component's model a file belongs to, from its data alone.

The router never reads column names. It computes a fingerprint of the table (shape, how values
are distributed, how they evolve with age within each unit) and an XGBoost classifier maps it to
turbofan, battery, bearing or unknown. Below the confidence threshold, or for unknown, the file is
not routed, so data never reaches a model it does not belong to.
"""

import json
from dataclasses import dataclass
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from src.config import MODEL_VERSION, MODELS_DIR

UNKNOWN = "unknown"
THRESHOLD = 0.8  # minimum class probability to route a file
MAX_ROWS = 20000  # fingerprints of larger files use a sample of whole units

# Fingerprint features with a readable description, used to explain a routing decision.
FEATURES = {
    "n_value_cols": "number of value columns",
    "log_rows": "number of rows (log)",
    "has_units": "has unit and age columns",
    "log_units": "number of units (log)",
    "log_rows_per_unit": "rows per unit (log)",
    "mag_q0": "smallest typical magnitude", "mag_q25": "lower typical magnitude", "mag_q50": "median typical magnitude",
    "mag_q75": "upper typical magnitude", "mag_q100": "largest typical magnitude",
    "frac_mag_lt1": "share of columns below 1", "frac_mag_1_10": "share of columns between 1 and 10",
    "frac_mag_10_100": "share of columns between 10 and 100", "frac_mag_100_1000": "share of columns between 100 and 1,000",
    "frac_mag_gt1000": "share of columns above 1,000",
    "frac_constant": "share of constant columns", "frac_integer": "share of whole-number columns",
    "frac_negative": "share of mostly negative columns",
    "cv_q25": "lower relative spread", "cv_q50": "median relative spread", "cv_q75": "upper relative spread",
    "autocorr_mean": "smoothness from one row to the next", "autocorr_min": "least smooth column",
    "trend_mean": "how strongly columns trend with age", "trend_max": "strongest trend with age",
    "kurt_median": "typical impulsiveness (kurtosis)", "kurt_max": "largest impulsiveness (kurtosis)",
    "skew_abs_median": "typical asymmetry",
    "corr_mean": "how strongly columns move together",
}
FEATURE_NAMES = list(FEATURES)


def _numeric(df):
    num = df.apply(pd.to_numeric, errors="coerce")
    num = num.dropna(axis=1, how="all").dropna(axis=0, how="all")
    return num


def _structure(num):
    """Detect a unit id column and an age column among the first two columns (name-agnostic)."""
    if num.shape[1] < 3:
        return None, None
    a, b = num.iloc[:, 0], num.iloc[:, 1]
    is_int = lambda s: s.notna().all() and np.allclose(s, np.round(s))  # noqa: E731
    if not (is_int(a) and is_int(b)):
        return None, None
    n_units = a.nunique()
    if n_units < 1 or n_units > len(num) / 2:
        return None, None
    increasing = (b.groupby(a).diff().dropna() > 0).mean() if len(num) > n_units else 0
    if increasing < 0.9:
        return None, None
    return num.columns[0], num.columns[1]


def fingerprint(df):
    """Order- and name-independent description of a table: dict of FEATURE_NAMES."""
    num = _numeric(df)
    if num.empty or num.shape[1] < 2:
        return None
    id_col, t_col = _structure(num)
    if id_col is not None and len(num) > MAX_ROWS:  # keep whole units
        units = num[id_col].drop_duplicates().sample(frac=1, random_state=0)
        keep, total = [], 0
        sizes = num[id_col].value_counts()
        for u in units:
            keep.append(u)
            total += sizes[u]
            if total >= MAX_ROWS:
                break
        num = num[num[id_col].isin(keep)]
    elif len(num) > MAX_ROWS:
        num = num.sample(MAX_ROWS, random_state=0)

    values = num.drop(columns=[c for c in (id_col, t_col) if c is not None])
    values = values.loc[:, values.notna().mean() > 0.5]
    if values.shape[1] == 0:
        return None
    v = values.to_numpy(dtype=float)
    med = np.nanmedian(v, axis=0)
    std = np.nanstd(v, axis=0)
    mag = np.log10(np.abs(med) + 1e-6)
    constant = std <= 1e-9 * (np.abs(med) + 1e-9)
    cv = np.log10(std / (np.abs(med) + 1e-6) + 1e-9)
    integer = np.array([np.allclose(c[~np.isnan(c)], np.round(c[~np.isnan(c)])) for c in v.T])
    z = (v - np.nanmean(v, axis=0)) / np.where(std > 0, std, 1)
    kurt = np.nanmean(z ** 4, axis=0)
    skew = np.nanmean(z ** 3, axis=0)

    if id_col is not None:
        unit = num[id_col].to_numpy()
        t = num[t_col].to_numpy(dtype=float)
        same = np.r_[False, unit[1:] == unit[:-1]]
        frame = pd.DataFrame(v)
        dv = frame.groupby(unit).transform("mean").to_numpy()
        dt = t - pd.Series(t).groupby(unit).transform("mean").to_numpy()
        xd = v - dv
        denom = np.sqrt(np.nansum(xd ** 2, axis=0) * np.nansum(dt ** 2)) + 1e-12
        trend = np.abs(np.nansum(xd * dt[:, None], axis=0) / denom)
        a, b = xd[1:][same[1:]], xd[:-1][same[1:]]
        auto = (np.nansum(a * b, axis=0) / (np.sqrt(np.nansum(a ** 2, axis=0) * np.nansum(b ** 2, axis=0)) + 1e-12)
                if len(a) else np.zeros(v.shape[1]))
        n_units = len(np.unique(unit))
    else:
        trend = np.zeros(v.shape[1])
        a, b = z[1:], z[:-1]
        auto = np.nanmean(a * b, axis=0) if len(a) else np.zeros(v.shape[1])
        n_units = 1
    live = ~constant
    corr = np.corrcoef(np.nan_to_num(z[:, live]).T) if live.sum() > 1 else np.zeros((1, 1))
    off = np.abs(corr[~np.eye(len(corr), dtype=bool)]) if corr.size > 1 else np.array([0.0])

    q = np.nanpercentile(mag, [0, 25, 50, 75, 100])
    cvq = np.nanpercentile(cv[live] if live.any() else cv, [25, 50, 75])
    absmed = np.abs(med)
    return {
        "n_value_cols": v.shape[1], "log_rows": np.log10(len(num)), "has_units": float(id_col is not None),
        "log_units": np.log10(n_units), "log_rows_per_unit": np.log10(len(num) / n_units),
        "mag_q0": q[0], "mag_q25": q[1], "mag_q50": q[2], "mag_q75": q[3], "mag_q100": q[4],
        "frac_mag_lt1": np.mean(absmed < 1), "frac_mag_1_10": np.mean((absmed >= 1) & (absmed < 10)),
        "frac_mag_10_100": np.mean((absmed >= 10) & (absmed < 100)),
        "frac_mag_100_1000": np.mean((absmed >= 100) & (absmed < 1000)), "frac_mag_gt1000": np.mean(absmed >= 1000),
        "frac_constant": np.mean(constant), "frac_integer": np.mean(integer), "frac_negative": np.mean(med < 0),
        "cv_q25": cvq[0], "cv_q50": cvq[1], "cv_q75": cvq[2],
        "autocorr_mean": float(np.nanmean(auto[live])) if live.any() else 0.0,
        "autocorr_min": float(np.nanmin(auto[live])) if live.any() else 0.0,
        "trend_mean": float(np.nanmean(trend[live])) if live.any() else 0.0,
        "trend_max": float(np.nanmax(trend[live])) if live.any() else 0.0,
        "kurt_median": float(np.nanmedian(kurt[live])) if live.any() else 0.0,
        "kurt_max": float(np.nanmax(kurt[live])) if live.any() else 0.0,
        "skew_abs_median": float(np.nanmedian(np.abs(skew[live]))) if live.any() else 0.0,
        "corr_mean": float(np.nanmean(off)),
    }


def vectorize(fp):
    return np.array([[fp[k] for k in FEATURE_NAMES]], dtype=float)


@dataclass
class ComponentRouter:
    model: object  # XGBClassifier over FEATURE_NAMES
    classes: list
    threshold: float = THRESHOLD
    metadata: dict = None

    def route(self, df):
        """{'component': key or None, 'label': class, 'confidence', 'probabilities', 'signals', 'reason'}."""
        fp = fingerprint(df)
        if fp is None:
            return {"component": None, "label": UNKNOWN, "confidence": 0.0, "probabilities": {},
                    "signals": [], "fingerprint": None, "reason": "too few numeric columns to recognise"}
        x = vectorize(fp)
        proba = self.model.predict_proba(x)[0]
        k = int(np.argmax(proba))
        label, conf = self.classes[k], float(proba[k])
        accepted = label != UNKNOWN and conf >= self.threshold
        return {
            "component": label if accepted else None, "label": label, "confidence": round(conf, 4),
            "probabilities": {c: round(float(p), 4) for c, p in zip(self.classes, proba)},
            "signals": self._signals(x, k, fp), "fingerprint": {k2: round(float(v), 4) for k2, v in fp.items()},
            "reason": ("recognised from the data" if accepted else
                       "not similar to any trained component" if label == UNKNOWN else
                       f"looks most like {label}, but only {conf:.0%} confident"),
        }

    def _signals(self, x, k, fp, top=4):
        """The fingerprint features that pushed this decision most (SHAP), in words."""
        try:
            import shap
            values = np.asarray(shap.TreeExplainer(self.model).shap_values(x))
            contrib = values[0, :, k] if values.ndim == 3 else values[k][0]
        except Exception:  # noqa: BLE001 - explanations are optional
            return []
        order = np.argsort(-contrib)[:top]
        return [{"feature": FEATURE_NAMES[i], "description": FEATURES[FEATURE_NAMES[i]],
                 "value": round(float(fp[FEATURE_NAMES[i]]), 3), "impact": round(float(contrib[i]), 3)}
                for i in order if contrib[i] > 0]


def router_dir(version=MODEL_VERSION):
    return MODELS_DIR / version / "router"


def save_router(router, version=MODEL_VERSION):
    folder = router_dir(version)
    folder.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": router.model, "classes": router.classes, "threshold": router.threshold},
                folder / "router.joblib", compress=3)
    (folder / "metadata.json").write_text(json.dumps(router.metadata or {}, indent=2), encoding="utf-8")
    return folder


@lru_cache(maxsize=2)
def load_router(version=MODEL_VERSION):
    """The trained router, or None if it has not been trained yet."""
    folder = router_dir(version)
    if not (folder / "router.joblib").exists():
        return None
    obj = joblib.load(folder / "router.joblib")
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8")) if (folder / "metadata.json").exists() else {}
    return ComponentRouter(model=obj["model"], classes=obj["classes"], threshold=obj["threshold"], metadata=meta)
