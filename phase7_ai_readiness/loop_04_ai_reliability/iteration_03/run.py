"""Run --select, then --evaluate. Selection never generates fresh test days."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from readymix.ai import calibration as cal, evaluation as ev, train_ready_model as tr
from readymix.ai.fallback import predict_rows
from readymix.ai.features import FEATURES
from readymix.ai.predictor import MODEL_DIR
from readymix.ai.training_data import build_split, load_ai_config


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["--select", "--evaluate"])
    # Positional names starting with -- are intentionally handled explicitly.
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in ("--select", "--evaluate"):
        raise SystemExit("Use --select or --evaluate")
    lc = json.loads((HERE / "config.json").read_text())
    b = joblib.load(MODEL_DIR / "site_ready_v2.joblib")
    cfg = load_ai_config()
    cfg["splits"] = lc["splits"]

    def data(name):
        frame, _ = build_split(cfg, name, "S8_ai_prediction_error" if name != "fresh_test" else None)
        return frame

    def parts(df):
        p = tr.predict_remaining(b["regressor"], df)
        lo, hi = cal.interval({"lo": b["q_lo"], "hi": b["q_hi"]}, b["conformal_margin"], df)
        confidence = b["confidence_model"].predict(hi - lo)
        ood = np.array([bool(cal.out_of_range(r, b["feature_ranges"])) for r in df[FEATURES].to_dict("records")])
        trigger = (confidence < lc["threshold"]) | ood
        return p, lo, hi, confidence, trigger

    lock_path = HERE / "selection.json"
    if mode == "--select":
        if lock_path.exists():
            raise SystemExit("Selection already locked; create a new iteration to change policy.")
        val = pd.read_csv(ROOT / "readymix/data/training/ready_val.csv")
        stress = data("stress_val")
        rows = []
        for name, df in (("val", val), ("stress_val", stress)):
            p, _, _, _, trigger = parts(df)
            for rule in lc["fallback_candidates"]:
                combo = np.where(trigger, predict_rows(df, rule), p)
                rows.append(dict(split=name, rule=rule, mae=ev.mae(df.remaining_min, combo),
                                 ai_mae=ev.mae(df.remaining_min, p), fallback_share=float(trigger.mean())))
        scores = {rule: np.mean([r["mae"] for r in rows if r["rule"] == rule]) for rule in lc["fallback_candidates"]}
        chosen = min(scores, key=scores.get)
        pd.DataFrame(rows).to_csv(HERE / "selection.csv", index=False)
        joblib.dump(dict(b, version="site_ready_v3_candidate", fallback=chosen,
                         fallback_on_low_confidence=True, fallback_on_out_of_range=True), HERE / "candidate.joblib")
        lock = dict(rule=chosen, config_sha256=digest(HERE / "config.json"),
                    bundle_sha256=digest(HERE / "candidate.joblib"), status="LOCKED_BEFORE_FRESH_EVALUATION")
        lock_path.write_text(json.dumps(lock, indent=2) + "\n")
        print(pd.DataFrame(rows).to_string(index=False), flush=True)
        print("LOCKED:", chosen, flush=True)
        return
    lock = json.loads(lock_path.read_text())
    assert lock["config_sha256"] == digest(HERE / "config.json")
    assert lock["bundle_sha256"] == digest(HERE / "candidate.joblib")
    b = joblib.load(HERE / "candidate.joblib")
    rows = []
    for name in ("fresh_test", "fresh_s8"):
        df = data(name)
        p, lo, hi, conf, trigger = parts(df)
        fb = predict_rows(df, lock["rule"])
        combo = np.where(trigger, fb, p)
        y = df.remaining_min.to_numpy()
        high = conf >= lc["threshold"]
        rows.append(dict(split=name, rows=len(df), ai_mae=ev.mae(y, p), combined_mae=ev.mae(y, combo),
                         fallback_mae=ev.mae(y, fb), rule_hist_mae=ev.mae(y, ev.baseline_remaining(df, "rule_hist")),
                         coverage=float(((y >= lo) & (y <= hi)).mean()),
                         confidence_ece=ev.ece(np.abs(y - p) <= b["confidence_tolerance_min"], conf),
                         high_mae=ev.mae(y[high], p[high]), low_mae=ev.mae(y[~high], p[~high]),
                         fallback_share=float(trigger.mean())))
        print(rows[-1], flush=True)
    test, stress = rows
    gates = dict(G1_interval_coverage=lc["gates"]["coverage_min"] <= test["coverage"] <= lc["gates"]["coverage_max"],
                 G2_confidence_calibrated=test["confidence_ece"] <= lc["gates"]["ece_max"],
                 G3_confidence_ranks_error=test["high_mae"] < test["low_mae"],
                 G4_fallback_safe=test["combined_mae"] < test["fallback_mae"] and stress["combined_mae"] <= stress["ai_mae"])
    pd.DataFrame(rows).to_csv(HERE / "metrics.csv", index=False)
    (HERE / "gates.json").write_text(json.dumps(gates, indent=2) + "\n")
    print(gates, flush=True)
    # Candidate is NOT promoted automatically: runtime contract and regression
    # tests are separate gates, and fresh evaluation cannot be used for tuning.
    raise SystemExit(0 if all(gates.values()) else 1)


if __name__ == "__main__":
    main()
