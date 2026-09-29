# site_state.py -- what a dispatcher can observe at a site before it is ready
# (skill.md section 6, pre-pour part)
"""One row per order every step_minutes, from planned ready - lookback until
the site is really ready (or planned + horizon). Each row only uses what
has happened by its timestamp.

Hidden process per order (drawn per day, never written):
    prep_start = actual_ready - prep_duration   (prep_duration unknown, 60-150 min)
    crew arrives around prep_start
Observable:
    crew_status        NOT_READY until the crew arrives, then READY
    prep_progress_pct  last foreman report: (report_time - prep_start) / prep_duration
                       + noise, rounded to 10 %, capped at 90 until ready;
                       reports come every 15-30 min, so it is also stale
    minutes_since_report
    pump_status        NONE (chute site) | READY | DOWN (from a PUMP_FAILURE
                       event's timestamp until shortly before ready)
    current_status     NOT_READY | PREPARING (crew on site) | DELAYED (past planned)
    delay_so_far_min   max(0, now - planned)
    weather            the day's weather

Not here: queue_length, current_truck_count, previous_unload_min -- they
depend on dispatch and come from the execution engine, not the world.

The signals are informative about the delay but never equal to it: two
unknowns (prep start and duration), stale and noisy reports. Loop 3 tests
this with a label-permutation check.
"""

from .common import min_to_iso, rng


def build_site_state(world, orders_gt, events, cfg, scenario, seed):
    sc = cfg["site_state"]
    step = cfg["simulation"]["step_minutes"]
    date = cfg["simulation"]["date"]
    sites = {s["site_id"]: s for s in world["sites"]}
    fail_t = {}
    for e in events:
        if e["event_type"] == "PUMP_FAILURE":
            h, m = e["timestamp"][11:13], e["timestamp"][14:16]
            fail_t[e["order_id"]] = int(h) * 60 + int(m)

    rows = []
    for gt in orders_gt:
        oid, sid = gt["order_id"], gt["site_id"]
        P = int(gt["planned_ready_time"][11:13]) * 60 + int(gt["planned_ready_time"][14:16])
        A = P + int(gt["ready_delay_min"])
        g = rng(seed, "site_state", oid)
        dur = float(g.uniform(*sc["prep_duration_min"]))
        prep_start = A - dur
        crew_at = prep_start + float(g.normal(0, sc["crew_arrival_sd_min"]))
        repair_at = A - int(g.integers(sc["pump_repair_before_ready_min"][0], sc["pump_repair_before_ready_min"][1] + 1))
        t0 = P - sc["lookback_min"]
        t0 -= t0 % step
        # foreman report times: irregular, drawn ahead so reports never depend on later rows
        reports, r_t = [], t0 - int(g.integers(0, sc["report_every_min"][1]))
        while r_t < P + sc["horizon_after_planned_min"]:
            frac = (r_t - prep_start) / dur
            val = max(0.0, min(1.0, frac)) * 100 + float(g.normal(0, sc["progress_noise_pct"]))
            val = sc["progress_round_pct"] * round(val / sc["progress_round_pct"])
            reports.append((r_t, int(min(90, max(0, val)))))
            r_t += int(g.integers(sc["report_every_min"][0], sc["report_every_min"][1] + 1))
        pump = sites[sid]["pump_available"]
        t = t0
        while t < A and t <= P + sc["horizon_after_planned_min"]:
            last = [r for r in reports if r[0] <= t]
            prog, since = (last[-1][1], t - last[-1][0]) if last else (0, None)
            crew = "READY" if t >= crew_at else "NOT_READY"
            if not pump:
                pstat = "NONE"
            elif oid in fail_t and fail_t[oid] <= t < repair_at:
                pstat = "DOWN"
            else:
                pstat = "READY"
            status = "DELAYED" if t > P else ("PREPARING" if crew == "READY" else "NOT_READY")
            rows.append({"timestamp": min_to_iso(date, t), "site_id": sid, "order_id": oid,
                         "planned_ready_time": gt["planned_ready_time"], "current_status": status,
                         "crew_status": crew, "prep_progress_pct": prog,
                         "minutes_since_report": "" if since is None else since,
                         "pump_status": pstat, "delay_so_far_min": max(0, t - P),
                         "weather": scenario["weather"]})
            t += step
    rows.sort(key=lambda r: (r["timestamp"], r["order_id"]))
    return rows
