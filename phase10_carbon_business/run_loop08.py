"""Loop 8: turn Phase 9 iteration 02 runs into fuel, CO2 and THB.

No simulation is re-run. Reads the locked Phase 9 logs + datasets, recomputes
physical quantities with readymix.application.impact, applies the sourced
factors (value/low/high) and compares policies with a paired day bootstrap.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from readymix.application.impact import CASES, breakdown, load_factors, monetize

CFG = json.loads((HERE / "config.json").read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def runs():
    src = ROOT / CFG["input_root"]
    metrics = pd.read_csv(ROOT / CFG["input_metrics"])
    factors = load_factors(ROOT / CFG["impact_config"])
    rows, mismatches = [], []
    for r in metrics.itertuples():
        log = json.loads((src / r.log_file).read_text())
        b = breakdown(log, src / "datasets" / f"{r.scenario}_world42_day{r.seed}")
        if (abs(b["fuel_l"] - r.fuel_liters) > 0.051 or abs(b["distance_km"] - r.total_distance_km) > 0.051
                or b["site_idle_min"] != r.site_idle_min):
            mismatches.append((r.seed, r.scenario, r.policy))
        base = dict(seed=r.seed, scenario=r.scenario, policy=r.policy, unserved_trips=r.unserved_trips,
                    total_waiting_min=r.total_waiting_min, **b, fuel_l_per_m3=b["fuel_l"] / b["delivered_m3"])
        for case in CASES:
            rows.append(dict(base, case=case, **monetize(b, factors[case])))
    return pd.DataFrame(rows), mismatches, factors


def paired(df, a, b, metric, scope):
    d = df[df.case == "value"]
    if scope == "excl_S6":
        d = d[d.scenario != "S6_high_demand"]
    w = d.pivot(index=["seed", "scenario"], columns="policy", values=metric)
    gain = (w[b] - w[a]).groupby("seed").mean().to_numpy()          # positive = a saves vs b
    rng = np.random.default_rng(CFG["bootstrap"]["seed"])
    s = rng.choice(gain, size=(CFG["bootstrap"]["resamples"], len(gain)), replace=True).mean(axis=1)
    lo, hi = np.quantile(s, [0.025, 0.975])
    return dict(system=a, baseline=b, scope=scope, metric=metric, baseline_mean=float(w[b].mean()),
                system_mean=float(w[a].mean()), saving_per_day=float(gain.mean()),
                saving_pct=float(gain.mean() / w[b].mean() * 100), ci95_low=float(lo), ci95_high=float(hi),
                verdict="saving" if lo > 0 else ("worse" if hi < 0 else "no clear difference"))


def main():
    df, mismatches, factors = runs()
    df.round(4).to_csv(HERE / "impact_runs.csv", index=False)
    days = factors["value"]["days_per_year"]

    v = df[df.case == "value"]
    carbon = v.groupby("policy")[["distance_km", "moving_fuel_l", "idle_fuel_l", "fuel_l", "co2_kg", "idle_co2_kg",
                                  "fuel_l_per_m3", "delivered_m3", "unserved_trips"]].mean()
    for case in ("low", "high"):
        carbon[f"co2_kg_{case}"] = df[df.case == case].groupby("policy")["co2_kg"].mean()
    carbon["co2_t_per_year"] = carbon["co2_kg"] * days / 1000
    carbon["co2_kg_per_m3"] = carbon["co2_kg"] / carbon["delivered_m3"]
    carbon.round(3).to_csv(HERE / "carbon_results.csv")

    biz = df.groupby(["policy", "case"])[["fuel_thb", "driver_wait_thb", "crew_idle_thb", "cost_proxy_thb",
                                          "driver_wait_h", "crew_idle_person_h", "unserved_trips"]].mean()
    biz["cost_proxy_thb_per_year"] = biz["cost_proxy_thb"] * days
    biz["driver_wait_h_per_year"] = biz["driver_wait_h"] * days
    biz.round(2).to_csv(HERE / "business_simulation.csv")

    comps = [paired(df, a, b, m, s) for a, b in CFG["comparisons"] for s in CFG["scopes"] for m in CFG["metrics"]
             + ["driver_wait_h", "crew_idle_person_h", "unserved_trips"]]
    comp = pd.DataFrame(comps)
    comp["saving_per_year"] = comp["saving_per_day"] * days
    comp.round(4).to_csv(HERE / "comparisons.csv", index=False)

    # sensitivity: cost/CO2 saving of each comparison under low/high factor cases (point estimate)
    sens = []
    for a, b in CFG["comparisons"]:
        for s in CFG["scopes"]:
            d = df if s == "all" else df[df.scenario != "S6_high_demand"]
            for case in CASES:
                g = d[d.case == case].groupby("policy")[["co2_kg", "cost_proxy_thb"]].mean()
                sens.append(dict(system=a, baseline=b, scope=s, case=case,
                                 co2_saving_kg_day=g.loc[b, "co2_kg"] - g.loc[a, "co2_kg"],
                                 cost_saving_thb_day=g.loc[b, "cost_proxy_thb"] - g.loc[a, "cost_proxy_thb"]))
    pd.DataFrame(sens).round(3).to_csv(HERE / "sensitivity.csv", index=False)

    cfg = yaml.safe_load((ROOT / CFG["impact_config"]).read_text(encoding="utf-8"))
    sourced = all(isinstance(i, dict) is False or (i.get("source_type") and (i.get("source") or i.get("derivation") or i.get("note")))
                  for g in ("carbon", "fuel", "labor", "annualization") for i in cfg[g].values())
    chain = True
    f = factors["value"]
    for a, b in CFG["comparisons"]:
        g = v.groupby("policy")[["moving_fuel_l", "idle_fuel_l", "fuel_l", "co2_kg"]].mean()
        dfuel = g.loc[b, "fuel_l"] - g.loc[a, "fuel_l"]
        parts = (g.loc[b, "moving_fuel_l"] - g.loc[a, "moving_fuel_l"]) + (g.loc[b, "idle_fuel_l"] - g.loc[a, "idle_fuel_l"])
        chain &= abs(dfuel - parts) < 1e-6 and abs((g.loc[b, "co2_kg"] - g.loc[a, "co2_kg"]) - dfuel * f["co2_kg_per_l"]) < 1e-6
    fe, idl = cfg["fuel"]["simulated_fuel_efficiency_km_l_range"], cfg["fuel"]["simulated_idle_fuel_l_h_range"]
    in_range = (fe[0] <= cfg["fuel"]["reference_fuel_efficiency_km_l"]["value"] <= fe[1]
                and idl[0] <= cfg["fuel"]["reference_idle_fuel_l_h"]["value"] <= idl[1])
    gates = dict(G1_provenance=bool(sourced), G2_independent_recompute=not mismatches,
                 G3_chain_closes=bool(chain), G4_placeholder_in_public_range=bool(in_range))
    lock = {p: sha(ROOT / p) for p in (CFG["input_metrics"], CFG["impact_config"], "readymix/application/impact.py",
                                       "phase10_carbon_business/config.json")}
    (HERE / "evaluation_lock.json").write_text(json.dumps(lock, indent=2))
    (HERE / "gates.json").write_text(json.dumps(dict(gates=gates, mismatches=mismatches, runs=int(len(v))), indent=2))
    pd.set_option("display.width", 250)
    print(carbon.round(2).to_string())
    print(comp[comp.metric.isin(["co2_kg", "cost_proxy_thb", "fuel_l_per_m3", "unserved_trips"])]
          [["system", "baseline", "scope", "metric", "saving_per_day", "saving_pct", "ci95_low", "ci95_high", "verdict"]].round(2).to_string())
    print(json.dumps(gates, indent=2))
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
