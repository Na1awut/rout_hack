# safe_dispatch.py -- one guarded entry point: check data, check fleet, dispatch, check plan
"""run_safely(root, ...) never raises for bad input; it returns a status:

  REJECTED_DATA  data_validator found problems -> nothing is dispatched
  OK             plan executed, validated, every trip delivered
  DEGRADED       plan executed and valid, but trips were left unserved,
                 the AI was unavailable (fell back to no-AI dispatch), or
                 the predictor failed on some calls (per-call fallback)
  INVALID_PLAN   the executed day broke a physical rule (a bug: must never happen)
  ERROR          an unexpected exception (a bug: must never happen)

The fleet pre-check (fleet_check.check_fleet) is attached to every answer,
so an overloaded day comes back as "need N more trucks", not as a crash.
"""
import traceback

from .buffered_dispatch import BufferedDispatch
from .data_validator import validate_dataset
from .execution_validator import validate_execution
from .fleet_check import check_fleet
from .kpi import compute_kpis


def run_safely(root, use_ai=True, model="site_ready_v3.joblib", first_buffer_min=5, next_buffer_min=15,
               predictor=None, step_min=5, **dispatch_kw):
    out = dict(status=None, messages=[], preflight=None, kpi=None, result=None, policy=None)
    try:
        problems = validate_dataset(root)
        if problems:
            out.update(status="REJECTED_DATA", messages=[f"ข้อมูลไม่ผ่านการตรวจ: {p}" for p in problems[:10]])
            return out
        out["preflight"] = check_fleet(root)
        if out["preflight"]["status"] != "OK":
            out["messages"].append(out["preflight"]["message"])
        if out["preflight"]["status"] == "NO_ORDERS":
            out["status"] = "OK"
            return out
        if use_ai and predictor is None:
            try:
                from readymix.ai.predictor import SiteReadyPredictor
                predictor = SiteReadyPredictor(model)
            except Exception as e:          # missing/corrupt model file, bad sklearn version...
                out["messages"].append(f"AI ใช้ไม่ได้ ({type(e).__name__}) ใช้ dispatch แบบไม่มี AI แทน")
                predictor = None
        policy = BufferedDispatch(predictor if use_ai else None, first_buffer_min, next_buffer_min,
                                  step_min=step_min, **dispatch_kw)
        out["policy"] = policy.name
        from readymix.simulation.executor import run_day
        result = run_day(root, policy, step_min)
        out["result"] = result
        issues = validate_execution(result, root)
        if issues:
            out.update(status="INVALID_PLAN", messages=out["messages"] + issues[:10])
            return out
        k = compute_kpis(result, root)
        out["kpi"] = k
        degraded = k["unserved_trips"] > 0 or (use_ai and predictor is None) or policy.failures > 0
        if k["unserved_trips"]:
            out["messages"].append(f"ส่งไม่ได้ {k['unserved_trips']} เที่ยว ({k['unserved_volume_m3']} m³)")
        if policy.failures:
            out["messages"].append(f"AI error {policy.failures} ครั้ง ใช้เวลาตามแผน + ประกาศแทนในครั้งนั้น")
        out["status"] = "DEGRADED" if degraded else "OK"
        return out
    except Exception as e:
        out.update(status="ERROR", messages=out["messages"] + [f"{type(e).__name__}: {e}", traceback.format_exc(limit=3)])
        return out
