# run_loop04.py -- Loop 4: intervals, confidence, fallback, output contract
"""  python phase7_ai_readiness/loop_04_ai_reliability/run_loop04.py

Needs Loop 3's bundle (site_ready_v1). Writes metrics.csv,
reliability.csv (confidence bins), fallback.csv, and the production
bundle readymix/ai/models/site_ready_v2.joblib + model_card_v2.json.
"""

import csv
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import sklearn
import yaml

HERE = Path(__file__).resolve().parent
DEV_ROOT = HERE.parents[1]
sys.path.insert(0, str(DEV_ROOT))

from readymix.ai import calibration as cal                          # noqa: E402
from readymix.ai import evaluation as ev                            # noqa: E402
from readymix.ai import train_ready_model as tr                     # noqa: E402
from readymix.ai.features import FEATURES                           # noqa: E402
from readymix.ai.predictor import MODEL_DIR, SiteReadyPredictor, validate_prediction   # noqa: E402
from readymix.ai.training_data import load_ai_config, load_splits   # noqa: E402
from readymix.simulation.build_dataset import load_configs, simulate   # noqa: E402
from readymix.simulation.common import iso_to_min                    # noqa: E402


def main():
    lc = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    cfg = load_ai_config()
    d = load_splits()
    trn, val, tst, s8 = d["train"][0], d["val"][0], d["test"][0], d["robust_s8"][0]
    v1 = joblib.load(MODEL_DIR / "site_ready_v1.joblib")
    reg = v1["regressor"]
    tol, thr = lc["confidence_tolerance_min"], lc["confidence_threshold"]
    M = []

    def rec(name, split, metric, value):
        M.append({"name": name, "split": split, "metric": metric,
                  "value": round(value, 4) if isinstance(value, float) else value})

    # 1. conformal interval
    qm = cal.fit_quantiles(cfg, trn, lc["interval"]["q_lo"], lc["interval"]["q_hi"])
    margin = cal.conformal_margin(qm, val, lc["interval"]["target_coverage"])
    rec("conformal_margin_min", "val", "value", margin)

    def cover(df):
        lo, hi = cal.interval(qm, margin, df)
        y = df.remaining_min.to_numpy(float)
        return float(np.mean((y >= lo) & (y <= hi))), float(np.mean(hi - lo)), hi - lo

    # 2. confidence from interval width, fit on validation
    _, _, wv = cover(val)
    conf_model = cal.fit_confidence(wv, np.abs(val.remaining_min - tr.predict_remaining(reg, val)), tol)
    ranges = cal.feature_ranges(trn)

    def parts(df):
        _, _, w = cover(df)
        p = tr.predict_remaining(reg, df)
        conf = conf_model.predict(w)
        fb = ev.baseline_remaining(df, lc["fallback"])
        ood = np.array([bool(cal.out_of_range(r, ranges)) for r in df[FEATURES].to_dict("records")])
        return p, conf, fb, ood

    def trigger(variant, conf, ood):
        on = lc["fallback_variants"][variant]
        return (("low_confidence" in on) & (conf < thr)) | (("out_of_range" in on) & ood)

    # choose the fallback variant on validation only
    pv, cv, fv, ov = parts(val)
    yv = val.remaining_min.to_numpy(float)
    for v in lc["fallback_variants"]:
        rec(f"variant_{v}", "val", "mae_all", ev.mae(yv, np.where(trigger(v, cv, ov), fv, pv)))
    order = list(lc["fallback_variants"])[::-1]                   # ties go to the variant with more safety
    chosen = min(order, key=lambda v: round(ev.mae(yv, np.where(trigger(v, cv, ov), fv, pv)), 4))
    rec("variant_chosen_on_val", "val", "choice", chosen)
    print(f"fallback variant chosen on validation: {chosen}")

    def score(df, split):
        cov, width, w = cover(df)
        p, conf, fb, ood = parts(df)
        err = np.abs(df.remaining_min.to_numpy(float) - p)
        hit = (err <= tol).astype(float)
        use_fb = trigger(chosen, conf, ood)
        combo = np.where(use_fb, fb, p)
        y = df.remaining_min.to_numpy(float)
        for v in lc["fallback_variants"]:
            rec(f"variant_{v}", split, "mae_all", ev.mae(y, np.where(trigger(v, conf, ood), fb, p)))
        rec("interval", split, "coverage", cov)
        rec("interval", split, "mean_width_min", width)
        rec("confidence", split, "ece", ev.ece(hit, conf))
        rec("confidence", split, "mean_confidence", float(conf.mean()))
        rec("confidence", split, "hit_rate_abs_err_le_tol", float(hit.mean()))
        hi_m, lo_m = conf >= thr, conf < thr
        rec("confidence", split, "mae_high_conf", ev.mae(y[hi_m], p[hi_m]) if hi_m.any() else float("nan"))
        rec("confidence", split, "mae_low_conf", ev.mae(y[lo_m], p[lo_m]) if lo_m.any() else float("nan"))
        rec("fallback", split, "share_fallback", float(use_fb.mean()))
        rec("fallback", split, "share_out_of_range", float(ood.mean()))
        for who, pred in (("ai", p), ("ai_plus_fallback", combo), ("fallback_rule", fb)):
            rec(who, split, "mae_all", ev.mae(y, pred))
            m45 = (df["t"] == df["planned"] - cfg["headline_lead_min"]).to_numpy()
            rec(who, split, f"mae_at_{cfg['headline_lead_min']}", ev.mae(y[m45], pred[m45]))
        bins = []
        edges = np.linspace(0, 1, 11)
        for i in range(10):
            m = (conf >= edges[i]) & ((conf < edges[i + 1]) if i < 9 else (conf <= 1))
            if m.any():
                bins.append({"split": split, "bin": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "rows": int(m.sum()),
                             "mean_confidence": round(float(conf[m].mean()), 3), "hit_rate": round(float(hit[m].mean()), 3)})
        return bins

    reliability = score(tst, "test") + score(s8, "robust_s8")

    # 3. save the production bundle
    bundle = dict(v1, version="site_ready_v2", q_lo=qm["lo"], q_hi=qm["hi"], conformal_margin=margin,
                  confidence_model=conf_model, confidence_threshold=thr, confidence_tolerance_min=tol,
                  feature_ranges=ranges, fallback=lc["fallback"],
                  fallback_on_low_confidence="low_confidence" in lc["fallback_variants"][chosen],
                  fallback_on_out_of_range="out_of_range" in lc["fallback_variants"][chosen])
    joblib.dump(bundle, MODEL_DIR / "site_ready_v2.joblib")
    card = json.loads((MODEL_DIR / "model_card_v1.json").read_text(encoding="utf-8"))
    card.update(model_version="site_ready_v2", conformal_margin_min=round(margin, 2), confidence_threshold=thr,
                confidence="P(|error| <= %d min), isotonic on interval width, fit on validation" % tol,
                fallback_variant=chosen,
                fallback="planned + announced + historical mean when triggered by: "
                         + (", ".join(lc["fallback_variants"][chosen]) or "never"),
                sklearn=sklearn.__version__)
    (MODEL_DIR / "model_card_v2.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    # 4. contract check through the real predictor, on raw simulated days
    pred = SiteReadyPredictor("site_ready_v2.joblib")
    sim_cfg, scen_cfg = load_configs()
    n_checked, contract_errors, fallback_reasons = 0, [], {}
    for split, force in (("test", None), ("robust_s8", "S8_ai_prediction_error")):
        from readymix.ai.training_data import day_scenario, split_days
        for day in split_days(cfg, split)[:10]:
            name = force or day_scenario(day, cfg["scenario_weights"])
            _, t = simulate(sim_cfg, scen_cfg, name, day, cfg["world_seed"])
            sites = {s["site_id"]: s for s in t["master/sites.csv"]}
            orders = {o["order_id"]: o for o in t["orders/orders.csv"]}
            for st in t["runtime/site_state.csv"]:
                p = pred.predict(st, sites[st["site_id"]], orders[st["order_id"]], t["runtime/events.json"],
                                 iso_to_min(st["timestamp"]), sim_cfg["simulation"]["date"])
                n_checked += 1
                e = validate_prediction(p)
                if e:
                    contract_errors.append((split, day, e))
                if p["fallback_used"]:
                    key = p["fallback_reason"].split(":")[0].split(" 0")[0]
                    fallback_reasons[key] = fallback_reasons.get(key, 0) + 1
    # malformed inputs must fall back, never raise
    st, site, order = dict(t["runtime/site_state.csv"][0]), sites[t["runtime/site_state.csv"][0]["site_id"]], \
        orders[t["runtime/site_state.csv"][0]["order_id"]]
    bad_ok = True
    for broken in ({**st, "current_status": "ON_FIRE"}, {**st, "prep_progress_pct": "n/a"}, {**st, "delay_so_far_min": 9999}):
        try:
            p = pred.predict(broken, site, order, [], iso_to_min(st["timestamp"]), sim_cfg["simulation"]["date"])
            bad_ok &= p["fallback_used"] and not validate_prediction(p)
        except Exception:
            bad_ok = False
    rec("contract", "test+robust_s8", "predictions_checked", n_checked)
    rec("contract", "test+robust_s8", "contract_errors", len(contract_errors))
    rec("contract", "malformed_inputs", "fall_back_without_raising", bad_ok)

    for fname, rows in (("metrics.csv", M), ("reliability.csv", reliability),
                        ("fallback.csv", [{"reason": k, "predictions": v} for k, v in sorted(fallback_reasons.items())] or
                         [{"reason": "none", "predictions": 0}])):
        with open(HERE / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    g = lambda n, s, m: next(r["value"] for r in M if (r["name"], r["split"], r["metric"]) == (n, s, m))   # noqa: E731
    gates = {
        "G1_interval_coverage": 0.75 <= g("interval", "test", "coverage") <= 0.85,
        "G2_confidence_calibrated": g("confidence", "test", "ece") <= 0.05,
        "G3_confidence_ranks_error": g("confidence", "test", "mae_high_conf") < g("confidence", "test", "mae_low_conf"),
        "G4_fallback_safe": (g("ai_plus_fallback", "test", "mae_all") < g("fallback_rule", "test", "mae_all")
                             and g("ai_plus_fallback", "robust_s8", "mae_all") <= g("ai", "robust_s8", "mae_all")),
        "G5_contract": len(contract_errors) == 0 and bad_ok,
    }
    for r in M:
        print(f"   {r['name']:18s} {r['split']:16s} {r['metric']:26s} {r['value']}")
    print("\nreliability (test):")
    for b in reliability:
        if b["split"] == "test":
            print("  ", b)
    print("fallback reasons (10 test + 10 S8 days):", fallback_reasons)
    print("\nGates:")
    for k, ok in gates.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {k}")
    ok = all(gates.values())
    print(f"\nLOOP 4 (G1-G5): {'PASS' if ok else 'FAIL'}   -- G6 run separately")
    return 0 if ok else 1


if __name__ == "__main__":
    # Keep the original implementation above as provenance; the canonical
    # entrypoint verifies the selected, locked v3 policy without overwriting v2.
    import runpy
    if len(sys.argv) == 1:
        sys.argv.append("--evaluate")
    runpy.run_path(str(HERE / "run_loop04_v3.py"), run_name="__main__")
