# train_ready_model.py -- Target A (ready time) and Target C (delay probability)
"""Candidates are fit on train days and chosen on validation days:
  ready time    RandomForest (squared error), HistGradientBoosting (squared / absolute error)
  delay prob    HistGradientBoosting classifier
predict remaining_min, clipped at 0. No deep learning (skill.md section 11).
"""

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestRegressor

from .features import FEATURES


def regressors(cfg):
    rf, gb, seed = cfg["models"]["random_forest"], cfg["models"]["gradient_boosting"], cfg["model_seed"]
    return {
        "random_forest": lambda: RandomForestRegressor(random_state=seed, n_jobs=-1, **rf),
        "hgb_l2": lambda: HistGradientBoostingRegressor(random_state=seed, loss="squared_error", **gb),
        "hgb_l1": lambda: HistGradientBoostingRegressor(random_state=seed, loss="absolute_error", **gb),
    }


def fit_regressor(make, df, features=FEATURES, target="remaining_min"):
    m = make()
    m.fit(df[features].to_numpy(float), df[target].to_numpy(float))
    return m


def predict_remaining(model, df, features=FEATURES):
    return np.maximum(0.0, model.predict(df[features].to_numpy(float)))


def fit_classifier(cfg, df, features=FEATURES):
    gb = cfg["models"]["gradient_boosting"]
    m = HistGradientBoostingClassifier(random_state=cfg["model_seed"], **gb)
    m.fit(df[features].to_numpy(float), df["late15"].to_numpy(int))
    return m


def predict_late_prob(model, df, features=FEATURES):
    p = model.predict_proba(df[features].to_numpy(float))[:, 1]
    # already more than 15 min past planned and still not ready: late for certain
    return np.where(df["delay_so_far_min"].to_numpy(float) > 15, 1.0, p)
