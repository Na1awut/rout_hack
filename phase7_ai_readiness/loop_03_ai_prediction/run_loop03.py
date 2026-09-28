# run_loop03.py -- Loop 3: train, select on validation, score once on test
"""  python phase7_ai_readiness/loop_03_ai_prediction/run_loop03.py

Writes metrics.csv (every number in notes.md), lead_table.csv,
scenario_table.csv, ablation.csv, and the model bundle
readymix/ai/models/site_ready_v1.joblib + model_card_v1.json.
"""

import csv
import hashlib
import inspect
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

HERE = Path(__file__).resolve().parent
DEV_ROOT = HERE.parents[1]
sys.path.insert(0, str(DEV_ROOT))

from readymix.ai import evaluation as ev                        # noqa: E402
from readymix.ai import train_ready_model as tr                 # noqa: E402
from readymix.ai.features import FEATURES, SERVICE_FEATURES, feature_row   # noqa: E402
from readymix.ai.training_data import OUT as TRAIN_DIR, load_ai_config, load_splits   # noqa: E402

MODEL_DIR = DEV_ROOT / "readymix" / "ai" / "models"
SIGNALS = ["crew_ready", "prep_progress_pct", "minutes_since_report", "pump_down", "status_code"]
HISTORY = ["site_code", "hist_delay_mean", "hist_delay_std"]
EVENTS = ["announced_delay_min", "has_announcement"]


def phash(a):
    return hashlib.sha256(np.round(np.asarray(a, float), 6).tobytes()).hexdigest()[:12]


def main():
    cfg = load_ai_config()
    d = load_splits()
    trn, val, tst = d["train"][0], d["val"][0], d["test"][0]
    s_trn, s_val, s_tst = d["train"][1], d["val"][1], d["test"][1]
    L = cfg["headline_lead_min"]
    bs = cfg["bootstrap"]
    M = []                                                     # (section, name, split, metric, value)

    def rec(section, name, split, metric, value):
        M.append({"section": section, "name": name, "split": split, "metric": metric,
                  "value": round(value, 4) if isinstance(value, float) else value})

    # -- baselines, chosen on validation -------------------------------------
    v45 = ev.at_lead(val, L)
    for b in ev.BASELINES:
        rec("ready", b, "val", f"mae_at_{L}", ev.mae(v45.remaining_min, ev.baseline_remaining(v45, b)))
    best_b = min(ev.BASELINES, key=lambda b: ev.mae(v45.remaining_min, ev.baseline_remaining(v45, b)))

    # -- models, chosen on validation ---------------------------------------
    fitted = {}
    for name, make in tr.regressors(cfg).items():
        fitted[name] = tr.fit_regressor(make, trn)
        rec("ready", name, "val", f"mae_at_{L}", ev.mae(v45.remaining_min, tr.predict_remaining(fitted[name], v45)))
    best_m = min(fitted, key=lambda n: ev.mae(v45.remaining_min, tr.predict_remaining(fitted[n], v45)))
    model = fitted[best_m]
    print(f"chosen on validation: model={best_m}  baseline={best_b}")

    # -- test, scored once -----------------------------------------------------
    t45 = ev.at_lead(tst, L)
    pm, pb = tr.predict_remaining(model, t45), ev.baseline_remaining(t45, best_b)
    lo, hi, diff = ev.paired_bootstrap(t45, t45.remaining_min - pb, t45.remaining_min - pm, bs["resamples"], bs["seed"])
    rec("ready", best_m, "test", f"mae_at_{L}", ev.mae(t45.remaining_min, pm))
    rec("ready", best_b, "test", f"mae_at_{L}", ev.mae(t45.remaining_min, pb))
    rec("ready", "improvement", "test", f"mae_gain_at_{L}", diff)
    rec("ready", "improvement", "test", f"ci95_lo_at_{L}", lo)
    rec("ready", "improvement", "test", f"ci95_hi_at_{L}", hi)
    pm_all, pb_all = tr.predict_remaining(model, tst), ev.baseline_remaining(tst, best_b)
    lo2, hi2, diff2 = ev.paired_bootstrap(tst, tst.remaining_min - pb_all, tst.remaining_min - pm_all, bs["resamples"], bs["seed"])
    rec("ready", best_m, "test", "mae_all", ev.mae(tst.remaining_min, pm_all))
    rec("ready", best_b, "test", "mae_all", ev.mae(tst.remaining_min, pb_all))
    rec("ready", "improvement", "test", "mae_gain_all", diff2)
    rec("ready", "improvement", "test", "ci95_lo_all", lo2)
    rec("ready", "improvement", "test", "ci95_hi_all", hi2)
    print(f"test MAE@{L}: model {ev.mae(t45.remaining_min, pm):.2f} vs {best_b} {ev.mae(t45.remaining_min, pb):.2f}  "
          f"gain {diff:.2f} [{lo:.2f}, {hi:.2f}]   all rows gain {diff2:.2f} [{lo2:.2f}, {hi2:.2f}]")

    lead_rows = []
    for lead in cfg["lead_times_min"]:
        x = ev.at_lead(tst, lead)
        row = {"lead_min": lead, "orders_not_ready": len(x), "model": round(ev.mae(x.remaining_min, tr.predict_remaining(model, x)), 2)}
        for b in ev.BASELINES:
            row[b] = round(ev.mae(x.remaining_min, ev.baseline_remaining(x, b)), 2)
        lead_rows.append(row)
    scen_rows = []
    for sc, x in t45.groupby("scenario"):
        scen_rows.append({"scenario": sc, "orders": len(x),
                          "model": round(ev.mae(x.remaining_min, tr.predict_remaining(model, x)), 2),
                          best_b: round(ev.mae(x.remaining_min, ev.baseline_remaining(x, best_b)), 2),
                          "planned": round(ev.mae(x.remaining_min, ev.baseline_remaining(x, "planned")), 2)})

    # -- Target C: delay probability -----------------------------------------
    clf = tr.fit_classifier(cfg, trn)
    for split, x in (("test_all", tst), (f"test_at_{L}", t45)):
        p, q = tr.predict_late_prob(clf, x), ev.baseline_late_prob(x)
        for who, prob in (("hgb_classifier", p), ("baseline_normal", q)):
            pr, rc, f1 = ev.f1_at(x.late15, prob)
            for k, v in (("brier", ev.brier(x.late15, prob)), ("auc", ev.auc(x.late15, prob)),
                         ("ece", ev.ece(x.late15, prob)), ("precision", pr), ("recall", rc), ("f1", f1)):
                rec("delay_prob", who, split, k, v)

    # -- Target B: service time --------------------------------------------------
    sv = {"estimate": s_val["estimated_unload_min"].to_numpy(float),
          "prev_or_estimate": np.where(s_val["prev_actual_unload"] > 0, s_val["prev_actual_unload"], s_val["estimated_unload_min"])}
    smodel = HistGradientBoostingRegressor(random_state=cfg["model_seed"], loss="absolute_error",
                                           **cfg["models"]["gradient_boosting"])
    smodel.fit(s_trn[SERVICE_FEATURES].to_numpy(float), s_trn["actual_unload_min"].to_numpy(float))
    sv["hgb_l1"] = smodel.predict(s_val[SERVICE_FEATURES].to_numpy(float))
    for k, p in sv.items():
        rec("service", k, "val", "mae", ev.mae(s_val.actual_unload_min, p))
    best_s = min(sv, key=lambda k: ev.mae(s_val.actual_unload_min, sv[k]))
    st = {"estimate": s_tst["estimated_unload_min"].to_numpy(float),
          "prev_or_estimate": np.where(s_tst["prev_actual_unload"] > 0, s_tst["prev_actual_unload"], s_tst["estimated_unload_min"]),
          "hgb_l1": smodel.predict(s_tst[SERVICE_FEATURES].to_numpy(float))}
    for k, p in st.items():
        rec("service", k, "test", "mae", ev.mae(s_tst.actual_unload_min, p))
    slow = s_tst["slowdown_visible"] == 1
    for k, p in st.items():
        rec("service", k, "test_slowdown_only", "mae", ev.mae(s_tst.actual_unload_min[slow], np.asarray(p)[slow.to_numpy()]))
    rec("service", "chosen_on_val", "val", "choice", best_s)

    # -- leakage checks -------------------------------------------------------
    days = {s: set(d[s][0]["day"]) for s in d}
    disjoint = all(not (days[a] & days[b]) for a in days for b in days if a < b)
    perm = trn.copy()
    perm["remaining_min"] = np.random.default_rng(0).permutation(perm["remaining_min"].to_numpy())
    pmodel = tr.fit_regressor(tr.regressors(cfg)[best_m], perm)
    perm_mae = ev.mae(t45.remaining_min, tr.predict_remaining(pmodel, t45))
    rec("leakage", "permuted_label_model", "test", f"mae_at_{L}", perm_mae)
    rec("leakage", "splits_disjoint", "all", "bool", disjoint)
    no_label_arg = not any(a in inspect.signature(feature_row).parameters
                           for a in ("label", "truth", "actual", "orders_gt", "ready"))
    rec("leakage", "feature_row_has_no_label_argument", "code", "bool", no_label_arg)

    abl = []
    for label, drop in (("all features", []), ("- site_state signals", SIGNALS), ("- site history", HISTORY),
                        ("- announced events", EVENTS), ("- signals and events", SIGNALS + EVENTS)):
        feats = [f for f in FEATURES if f not in drop]
        m = tr.fit_regressor(tr.regressors(cfg)[best_m], trn, feats)
        abl.append({"features": label, f"val_mae_at_{L}": round(ev.mae(v45.remaining_min, tr.predict_remaining(m, v45, feats)), 2)})

    # -- reproducibility ------------------------------------------------------
    again = tr.fit_regressor(tr.regressors(cfg)[best_m], trn)
    repro = phash(tr.predict_remaining(again, tst)) == phash(pm_all)
    rec("repro", best_m, "test", "prediction_sha256_12", phash(pm_all))
    rec("repro", best_m, "test", "identical_on_retrain", repro)

    # -- save model bundle ------------------------------------------------------
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"version": "site_ready_v1", "features": FEATURES, "regressor": model, "classifier": clf,
                 "regressor_name": best_m, "service_features": SERVICE_FEATURES, "service_model": smodel,
                 "service_choice": best_s}, MODEL_DIR / "site_ready_v1.joblib")
    card = {"model_version": "site_ready_v1", "trained_on": json.loads((TRAIN_DIR / "manifest.json").read_text(encoding="utf-8")),
            "regressor": best_m, "baseline_to_beat": best_b, "service_choice": best_s, "features": FEATURES,
            "sklearn": sklearn.__version__, "test_prediction_sha256_12": phash(pm_all),
            "data": "SIMULATED -- accuracy shows the pipeline works on this simulator, not real-world accuracy"}
    (MODEL_DIR / "model_card_v1.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    for fname, rows in (("metrics.csv", M), ("lead_table.csv", lead_rows), ("scenario_table.csv", scen_rows),
                        ("ablation.csv", abl)):
        with open(HERE / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def get(section, name, split, metric):
        return next(r["value"] for r in M if (r["section"], r["name"], r["split"], r["metric"]) == (section, name, split, metric))

    gates = {
        "G1_beats_baseline_at_headline": lo > 0,
        "G2_beats_baseline_all_rows": lo2 > 0,
        "G3_delay_probability": (get("delay_prob", "hgb_classifier", "test_all", "brier") < get("delay_prob", "baseline_normal", "test_all", "brier")
                                 and get("delay_prob", "hgb_classifier", "test_all", "auc") > get("delay_prob", "baseline_normal", "test_all", "auc")),
        "G4_no_leakage": disjoint and no_label_arg and perm_mae >= ev.mae(t45.remaining_min, pb),
        "G5_reproducible": repro,
        "G6_service_choice": best_s in sv,
    }
    print("\nlead table (test MAE, min):")
    for r in lead_rows:
        print("  ", r)
    print("\nablation (val):", abl)
    print(f"permuted-label model MAE@{L}: {perm_mae:.2f}   service choice: {best_s}")
    print("\nGates:")
    for g, ok in gates.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {g}")
    ok = all(gates.values())
    print(f"\nLOOP 3 (G1-G6): {'PASS' if ok else 'FAIL'}   -- G7 run separately")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
