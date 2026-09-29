"""Replay one simulated day for the dashboard, keeping every decision's reason.

Nothing here changes a policy: TracingPredictor only records what the frozen
predictor returned, so a traced run produces the same execution log as the
Phase 9 evaluation run (the dashboard shows that check).
"""
import csv
import hashlib
import json
from pathlib import Path

from readymix.ai.predictor import SiteReadyPredictor
from readymix.application.buffered_dispatch import BufferedDispatch
from readymix.application.dispatch_policies import StaticPlanned
from readymix.application.impact import breakdown, load_factors, monetize
from readymix.application.kpi import compute_kpis
from readymix.simulation.executor import run_day

ROOT = Path(__file__).resolve().parents[2]
PHASE9 = ROOT / "phase9_baseline_comparison" / "iteration_02"
PHASES = ("load_start", "depart", "arrive", "unload_start", "unload_end", "back", "free")
STATES = ("waiting for bay", "loading", "to site", "waiting at site", "unloading", "returning", "washing")


class TracingPredictor:
    """Pass-through wrapper that keeps every prediction the policy asked for."""

    def __init__(self, inner):
        self.inner, self.records = inner, []

    def predict(self, state, site, order, events, t, date):
        p = self.inner.predict(state, site, order, events, t, date)
        self.records.append(dict(t=t, **p))
        return p


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hhmm(minutes):
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def iso_min(iso):
    return int(iso[11:13]) * 60 + int(iso[14:16])


def dataset_root(scenario, seed):
    return PHASE9 / "datasets" / f"{scenario}_world42_day{seed}"


def run_traced(scenario, seed, policy="C_ai_rolling_buffered", model=None):
    """Run one policy on one Phase 9 eval day; return log, KPIs, impact and decisions."""
    cfg = json.loads((PHASE9 / "config.json").read_text())
    sel = json.loads((PHASE9 / "selection.json").read_text())
    root = dataset_root(scenario, seed)
    common = {k: cfg[k] for k in ("refresh_min", "step_min", "waiting_weight", "late_weight")}
    tracer = None
    if policy == "A_static_planned":
        pol = StaticPlanned(cfg["step_min"])
    else:
        predictor = None
        if policy.startswith("C_"):
            tracer = TracingPredictor(model or SiteReadyPredictor(cfg["model"]))
            predictor = tracer
        s = sel[policy]
        pol = BufferedDispatch(predictor, s["first_buffer_min"], s["next_buffer_min"], **common)
    result = run_day(root, pol, cfg["step_min"])
    log_json = json.dumps(result["log"], sort_keys=True)
    expected = _expected_hash(scenario, seed, policy)
    k = compute_kpis(result, root)
    b = breakdown(result["log"], root)
    money = monetize(b, load_factors()["value"])
    return dict(scenario=scenario, seed=seed, policy=policy, root=root, plan=result["plan"], log=result["log"],
                kpi=k, impact=dict(b, **money), audit=list(getattr(pol, "audit", [])),
                predictions=tracer.records if tracer else [],
                log_sha256=hashlib.sha256(log_json.encode()).hexdigest(), expected_sha256=expected)


def _expected_hash(scenario, seed, policy):
    for r in _rows(PHASE9 / "metrics.csv"):
        if r["scenario"] == scenario and int(r["seed"]) == seed and r["policy"] == policy:
            return r["log_sha256"]
    return None


def truck_states(log, t):
    """State of every truck that has a trip touching minute t (else idle at plant)."""
    out = {}
    for tid, lg in log.items():
        if "released" not in lg or lg["released"] > t or "truck" not in lg:
            continue
        marks = [lg["released"]] + [lg.get(k) for k in PHASES]
        for i, state in enumerate(STATES):
            a, b = marks[i], marks[i + 1]
            if a is not None and b is not None and a <= t < b:
                out[lg["truck"]] = dict(truck=lg["truck"], trip_id=tid, state=state, since=a, until=b)
                break
    return out


def decisions(run):
    """One record per released load, in the shape of skill.md section 33."""
    plan, log = run["plan"], run["log"]
    trips = {t["trip_id"]: t for t in plan.trips}
    preds = {}
    for p in run["predictions"]:
        preds.setdefault(p["order_id"], []).append(p)
    out = []
    for row in run["audit"]:
        tid = row["trip_id"]
        oid, sid = trips[tid]["order_id"], trips[tid]["site_id"]
        known = [p for p in preds.get(oid, []) if p["t"] <= row["t"]]
        last = known[-1] if known else None
        reason = dict(readiness_source=row["source"], target_arrival=hhmm(row["target"]),
                      planned_ready=plan.orders[oid]["requested_start"][11:16])
        if last is not None:
            reason.update(predicted_site_ready=last["predicted_ready_time"][11:16],
                          delay_probability=round(last["delay_probability"], 2),
                          confidence=round(last["confidence"], 2), fallback_used=last["fallback_used"])
        out.append(dict(timestamp=hhmm(row["t"]), vehicle=log[tid].get("truck", "-"), action="RELEASE_LOAD",
                        trip_id=tid, site=sid, departure_time=hhmm(log[tid].get("depart", row["release"])),
                        reason=reason))
    return out


def site_status(run, t):
    """Per order at minute t: planned vs latest AI prediction vs (revealed) actual."""
    plan, log = run["plan"], run["log"]
    truth = {r["order_id"]: r for r in _rows(run["root"] / "ground_truth/order_readiness.csv")}
    by_order = {}
    for tr in plan.trips:
        by_order.setdefault(tr["order_id"], []).append(tr["trip_id"])
    latest = {}
    for p in run["predictions"]:
        if p["t"] <= t:
            latest[p["order_id"]] = p
    rows = []
    for oid, o in sorted(plan.orders.items()):
        tids = by_order.get(oid, [])
        actual = iso_min(truth[oid]["actual_ready_time"])
        p = latest.get(oid)
        done = sum(1 for x in tids if log[x].get("unload_end", 1e9) <= t)
        unloading = any(log[x].get("unload_start", 1e9) <= t < log[x].get("unload_end", -1) for x in tids)
        waiting = sum(1 for x in tids if log[x].get("arrive", 1e9) <= t < log[x].get("unload_start", 1e9))
        rows.append(dict(order=oid, site=o["site_id"], planned_ready=o["requested_start"][11:16],
                         ai_predicted_ready=p["predicted_ready_time"][11:16] if p else "-",
                         delay_risk=round(p["delay_probability"], 2) if p else None,
                         actual_ready=hhmm(actual) if actual <= t else "not yet",
                         loads_done=f"{done}/{len(tids)}", unloading=unloading, trucks_waiting=waiting,
                         predicted_min=iso_min(p["predicted_ready_time"]) if p else None,
                         planned_min=o["requested_start_min"]))
    return rows


def alerts(run, t):
    out = []
    for s in site_status(run, t):
        if s["actual_ready"] == "not yet" and s["predicted_min"] is not None and s["predicted_min"] - s["planned_min"] >= 15 \
                and s["delay_risk"] is not None and s["delay_risk"] >= 0.5:
            out.append(f"{s['order']} @ {s['site']}: AI expects ready {s['ai_predicted_ready']} "
                       f"(planned {s['planned_ready']}, delay risk {s['delay_risk']:.0%})")
    for truck, st in sorted(truck_states(run["log"], t).items()):
        if st["state"] == "waiting at site" and t - st["since"] >= 15:
            out.append(f"{truck} waiting {t - st['since']} min at site ({st['trip_id']})")
    return out
