"""Optuna search over XGBoost settings, cross-validated by engine unit."""

import numpy as np
import optuna
from sklearn.metrics import f1_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold

from src.config import CV_FOLDS, OPTUNA_TRIALS, SEED

optuna.logging.set_verbosity(optuna.logging.WARNING)  # suppress per-trial progress spam


def _suggest(trial):
    return {
        "n_estimators": trial.suggest_int("n_estimators", 150, 600, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
    }


def tune(make_model, X, y, groups, task, n_trials=OPTUNA_TRIALS):
    """Return the best params. task='regression' minimises RMSE, 'classification' maximises macro F1."""
    folds = list(GroupKFold(n_splits=CV_FOLDS).split(X, y, groups))

    def objective(trial):
        params = _suggest(trial)
        scores = []
        for train_idx, test_idx in folds:
            model = make_model(params).fit(X.iloc[train_idx], y[train_idx])
            if task == "regression":
                scores.append(root_mean_squared_error(y[test_idx], model.predict(X.iloc[test_idx])))
            else:
                pred = model.predict_proba(X.iloc[test_idx]).argmax(axis=1)
                scores.append(f1_score(y[test_idx], pred, average="macro"))
        return float(np.mean(scores))

    direction = "minimize" if task == "regression" else "maximize"
    study = optuna.create_study(direction=direction, sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, study.best_value
