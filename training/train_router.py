"""Train the component-recognition model (src/router/) on fingerprints of many table slices.

Positive examples are random slices of each component's training files: a random subset of
units, each cut at a random age, with some value columns dropped and slight noise. Unknown
examples are unrelated tables: scikit-learn's toy datasets and synthetic sensor-like tables
(random scales, trends, random walks). The model is scored on slices of the test files, whose
units it never saw, and on fresh unknown tables.

Usage: python -m training.train_router   (also run by python -m training.train)
"""

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix
from xgboost import XGBClassifier

from src.components import COMPONENTS, spec_of_profile, to_canonical
from src.config import MODEL_VERSION, SEED
from src.data.loader import data_file, read_sensor_file
from src.router import FEATURE_NAMES, THRESHOLD, UNKNOWN, ComponentRouter, fingerprint, load_router, save_router

log = logging.getLogger("aerosentinel.router")
CLASSES = [*COMPONENTS, UNKNOWN]
SLICES_PER_FILE = {"train": 220, "test": 80}


def _table(profile, kind):
    path = data_file(kind, profile)
    if kind == "sample":
        path = path.with_name(f"sample_{profile}.csv")
    if not path.exists():
        return None
    return to_canonical(read_sensor_file(path), spec_of_profile(profile))


def slice_table(df, rng):
    """A random realistic upload: some units, each cut at a random age, some value columns missing."""
    units = df["unit"].unique()
    k = int(rng.integers(1, min(len(units), 80) + 1))
    chosen = rng.choice(units, size=k, replace=False)
    parts = []
    for u in chosen:
        part = df[df["unit"] == u].sort_values("cycle")
        end = int(rng.integers(min(len(part), 8), len(part) + 1))
        parts.append(part.iloc[:end])
    out = pd.concat(parts, ignore_index=True)
    values = [c for c in out.columns if c not in ("unit", "cycle")]
    drop = rng.choice(values, size=int(rng.integers(0, max(1, len(values) // 4) + 1)), replace=False)
    out = out.drop(columns=list(drop))
    noisy = [c for c in out.columns if c not in ("unit", "cycle")]
    out[noisy] = out[noisy] * rng.normal(1.0, 0.01, size=(len(out), len(noisy)))
    if rng.random() < 0.1:  # occasionally no unit/age structure at all
        out = out.drop(columns=["unit", "cycle"])
    return out


def synthetic_unknown(rng):
    """A table that is not from any trained component."""
    kind = rng.integers(0, 4)
    if kind == 0:  # scikit-learn toy datasets: real but unrelated tabular data
        from sklearn import datasets
        loader = [datasets.load_diabetes, datasets.load_wine, datasets.load_breast_cancer,
                  datasets.load_iris, datasets.load_linnerud][int(rng.integers(0, 5))]
        data = loader()
        df = pd.DataFrame(np.column_stack([data.data, np.ravel(data.target)[: len(data.data)][:, None]]
                                          if np.ndim(data.target) == 1 else data.data))
        return df.sample(frac=rng.uniform(0.3, 1.0), random_state=int(rng.integers(1e9)))
    n_units = int(rng.integers(1, 40))
    n_cols = int(rng.integers(3, 30))
    rows = []
    for u in range(1, n_units + 1):
        n = int(rng.integers(10, 400))
        t = np.arange(1, n + 1)
        cols = []
        for _ in range(n_cols):
            scale = 10 ** rng.uniform(-3, 5)
            shape = rng.integers(0, 4)
            if shape == 0:
                c = rng.normal(scale, scale * rng.uniform(0.001, 1), n)
            elif shape == 1:
                c = scale + np.cumsum(rng.normal(0, scale * 0.01, n))
            elif shape == 2:
                c = scale * (1 + rng.uniform(-0.5, 0.5) * t / n) + rng.normal(0, scale * 0.02, n)
            else:
                c = scale * np.sin(t / rng.uniform(2, 50)) + rng.normal(0, scale * 0.1, n)
            cols.append(c)
        rows.append(np.column_stack([np.full(n, u), t, *cols]))
    df = pd.DataFrame(np.vstack(rows))
    if kind == 3:
        df = df.iloc[:, 2:]  # no unit/age structure
    return df


def build_examples(kind, rng):
    X, y = [], []
    for spec in COMPONENTS.values():
        for profile in spec.profiles:
            sources = [_table(profile, kind)] + ([_table(profile, "sample")] if kind == "test" else [])
            for df in [s for s in sources if s is not None]:
                n = SLICES_PER_FILE[kind] // max(1, len(spec.profiles) // 2)
                for _ in range(n):
                    fp = fingerprint(slice_table(df, rng))
                    if fp is not None:
                        X.append([fp[k] for k in FEATURE_NAMES])
                        y.append(spec.key)
    n_unknown = int(len(y) * 0.5)
    while sum(1 for v in y if v == UNKNOWN) < n_unknown:
        fp = fingerprint(synthetic_unknown(rng))
        if fp is not None:
            X.append([fp[k] for k in FEATURE_NAMES])
            y.append(UNKNOWN)
    return np.array(X, dtype=float), np.array(y)


def train_router():
    rng = np.random.default_rng(SEED)
    X_train, y_train = build_examples("train", rng)
    X_test, y_test = build_examples("test", rng)
    log.info("Router examples: %d train, %d test", len(y_train), len(y_test))
    codes = {c: i for i, c in enumerate(CLASSES)}
    model = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.1, subsample=0.9, colsample_bytree=0.8,
                          tree_method="hist", random_state=SEED, n_jobs=-1)
    model.fit(X_train, np.array([codes[v] for v in y_train]))

    proba = model.predict_proba(X_test)
    pred = np.array(CLASSES)[proba.argmax(axis=1)]
    conf = proba.max(axis=1)
    routed = (pred != UNKNOWN) & (conf >= THRESHOLD)
    known = y_test != UNKNOWN
    metrics = {
        "test_examples": int(len(y_test)),
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "per_class_recall": {c: round(float(np.mean(pred[y_test == c] == c)), 4) for c in CLASSES},
        "confusion_matrix": confusion_matrix(y_test, pred, labels=CLASSES).tolist(),
        "classes": CLASSES,
        "threshold": THRESHOLD,
        # Of files from a known component: routed to the right model / held back / sent to a wrong model.
        "known_routed_correctly": round(float(np.mean(routed[known] & (pred[known] == y_test[known]))), 4),
        "known_held_back": round(float(np.mean(~routed[known])), 4),
        "known_misrouted": round(float(np.mean(routed[known] & (pred[known] != y_test[known]))), 4),
        "unknown_rejected": round(float(np.mean(~routed[~known])), 4),
    }
    log.info("Router test metrics: %s", {k: v for k, v in metrics.items() if k != "confusion_matrix"})
    meta = {"version": MODEL_VERSION, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "classes": CLASSES, "threshold": THRESHOLD, "features": FEATURE_NAMES, "metrics": metrics,
            "train_examples": int(len(y_train)),
            "note": "Trained on slices of training files; scored on slices of test and sample files (unseen units)."}
    save_router(ComponentRouter(model=model, classes=CLASSES, threshold=THRESHOLD, metadata=meta))
    load_router.cache_clear()
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    train_router()
