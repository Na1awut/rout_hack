"""Extract a compact, honest replay bundle from real Phase 9 day-9101 logs.

Every number here is read from already-published, hash-verified experiment
files (phase9_baseline_comparison/iteration_02). Nothing is simulated fresh;
this only re-projects real per-trip timestamps into a shape a browser can
animate. KPI running totals are attributed to the exact events kpi.py itself
sums over, so the end-of-day total equals the audited metrics.csv value
(checked below).
"""
import csv
import json
from pathlib import Path
import sys

ROOT = Path("/home/user/rout_hack")
sys.path.insert(0, str(ROOT))
from readymix.simulation.common import planar_km, hhmm_to_min, iso_to_min

ITER = ROOT / "phase9_baseline_comparison/iteration_02"
DAY = 9101
SCENARIOS = ["S0_normal", "S1_light_traffic", "S2_peak_traffic", "S3_site_delay",
             "S4_multi_site_delay", "S5_pump_failure", "S6_high_demand",
             "S7_mixed_disruption", "S8_ai_prediction_error"]
POLICIES = ["A_static_planned", "B_dynamic_buffered", "C_ai_rolling_buffered"]
LABELS = {"S0_normal": "S0 · วันปกติ", "S1_light_traffic": "S1 · รถไม่ติด",
          "S2_peak_traffic": "S2 · รถติดหนัก", "S3_site_delay": "S3 · ไซต์ล่าช้า",
          "S4_multi_site_delay": "S4 · หลายไซต์ล่าช้า", "S5_pump_failure": "S5 · ปั๊มเสีย",
          "S6_high_demand": "S6 · งานล้นรถ", "S7_mixed_disruption": "S7 · หลายเหตุการณ์",
          "S8_ai_prediction_error": "S8 · AI ทายผิด"}
# What each scenario injects (readymix/config/scenarios.yaml) and where to look.
SCENARIO_INFO = {
    "S0_normal": ("วันทำงานปกติ ไม่มีเหตุการณ์พิเศษ ไซต์พร้อมเร็วหรือช้ากว่านัดตามนิสัยของแต่ละไซต์",
                  "ดูว่าแต่ละระบบใช้รถรอที่ไซต์ (สีแดง) มากน้อยแค่ไหนในวันธรรมดา"),
    "S1_light_traffic": ("รถติดน้อยกว่าปกติครึ่งหนึ่ง รถไปถึงไซต์เร็วขึ้น",
                         "รถที่ถึงเร็วแต่ไซต์ยังไม่พร้อมจะกลายเป็นสีแดง ดูว่าระบบไหนรอน้อยกว่า"),
    "S2_peak_traffic": ("รถติดหนักกว่าปกติ 1.8 เท่า และมีช่วงรถติดพุ่ง 2 ครั้ง",
                        "เวลาเดินทางยาวขึ้น ไซต์เสี่ยงว่างรอรถ ดูวงแหวนไซต์สีเหลือง (พร้อมแต่รถยังไม่ถึง)"),
    "S3_site_delay": ("ไซต์ 1 แห่งแจ้งล่าช้า 30–60 นาที (ประกาศล่วงหน้าก่อนเวลานัด)",
                      "ดูไซต์ที่ถูกแจ้งล่าช้าใน Event Log แล้วเทียบว่าฝั่งไหนส่งรถไปรอเก้อ"),
    "S4_multi_site_delay": ("ไซต์ 3 แห่งแจ้งล่าช้าในวันเดียวกัน",
                            "หลายไซต์ล่าช้าพร้อมกัน ระบบที่ปรับแผนได้ควรกระจายรถไปไซต์ที่พร้อมก่อน"),
    "S5_pump_failure": ("ปั๊มคอนกรีตที่ไซต์ 1 แห่งเสีย ล่าช้า 45–90 นาที",
                        "ดูว่ารถที่ออกไปก่อนปั๊มเสียต้องจอดรอนานแค่ไหน"),
    "S6_high_demand": ("งานเพิ่ม 40% และมี order เพิ่ม 5 งาน เกินกำลังรถ 15 คัน",
                       "วันนี้รถไม่พอ ดูจำนวน 'ส่งแล้ว' ตอนจบวัน ระบบ AI ไม่ได้ช่วยในกรณีนี้"),
    "S7_mixed_disruption": ("ฝนตก รถติด ไซต์ล่าช้า 2 แห่ง ปั๊มเสีย รถเสีย 1 คัน เทช้า และปริมาณงานเปลี่ยน รวมในวันเดียว",
                            "วันที่วุ่นที่สุด ดู Event Log ประกอบว่าเหตุการณ์ไหนทำให้รถต้องรอ"),
    "S8_ai_prediction_error": ("ไซต์ที่ปกติตรงเวลา 2 แห่งพร้อมช้ากว่านัดมาก และไซต์ที่ปกติช้า 2 แห่งพร้อมเร็ว — ตั้งใจให้ AI ทายผิด",
                               "ทดสอบว่าเมื่อประวัติหลอก AI ระบบยังไม่แย่กว่าแผนเดิม"),
}
FIELDS = ["trips", "delivered_trips", "unserved_trips", "unserved_volume_m3", "total_waiting_min", "site_idle_min",
          "on_time_rate", "late_arrivals", "pour_gaps_over_30", "operational_score_min"]
IMPACT_FIELDS = ["fuel_l", "co2_kg", "cost_proxy_thb"]

POLICY_LABEL = {"A_static_planned": "A · แผนตายตัว", "B_dynamic_buffered": "B · ปรับแผน ไม่มี AI",
                "C_ai_rolling_buffered": "C · AI + Optimizer"}
EVENT_TEXT = {
    "SITE_DELAY": lambda e: f"ไซต์ {e['site_id']} แจ้งล่าช้า {e['delay_min']} นาที",
    "PUMP_FAILURE": lambda e: f"ไซต์ {e['site_id']} ปั๊มเสีย ล่าช้า {e['delay_min']} นาที",
    "SERVICE_SLOWDOWN": lambda e: f"ไซต์ {e['site_id']} เทช้าลง x{e['factor']}",
    "TRAFFIC_SPIKE": lambda e: f"รถติดพุ่งช่วง {', '.join(e['site_ids'])}",
    "TRUCK_BREAKDOWN": lambda e: f"รถ {e['vehicle_id']} เสีย",
    "DEMAND_CHANGE": lambda e: f"ไซต์ {e['site_id']} ปรับปริมาณงาน",
    "SITE_READY_EARLY": lambda e: f"ไซต์ {e['site_id']} พร้อมเร็วกว่านัด {e['early_min']} นาที",
    "SITE_READY_LATE": lambda e: f"ไซต์ {e['site_id']} พร้อมช้ากว่านัด {e['delay_min']} นาที",
}


def _rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dataset_root(scenario):
    return ITER / "datasets" / f"{scenario}_world42_day{DAY}"


def build_world(scenario):
    root = dataset_root(scenario)
    plant = _rows(root / "master/plants.csv")[0]
    lat0, lon0 = float(plant["latitude"]), float(plant["longitude"])
    sites = {}
    for s in _rows(root / "master/sites.csv"):
        x, y = planar_km(lat0, lon0, float(s["latitude"]), float(s["longitude"]))
        sites[s["site_id"]] = dict(id=s["site_id"], x=round(x, 3), y=round(y, 3),
                                   crew=int(s["crew_size"]), pump=s["pump_available"] == "true")
    vehicles = _rows(root / "master/vehicles.csv")
    trucks = {v["vehicle_id"]: dict(id=v["vehicle_id"], available=hhmm_to_min(v["available_from"][11:]))
              for v in vehicles}
    return dict(plant=dict(id=plant["plant_id"], x=0, y=0, open=hhmm_to_min(plant["operating_start"]),
                           close=hhmm_to_min(plant["operating_end"])),
                sites=sites, trucks=trucks)


def build_scenario(scenario):
    root = dataset_root(scenario)
    orders = {o["order_id"]: o for o in _rows(root / "orders/orders.csv")}
    trips = _rows(root / "orders/trips.csv")
    truth = {r["order_id"]: iso_to_min(r["actual_ready_time"]) for r in _rows(root / "ground_truth/order_readiness.csv")}
    events_raw = json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))
    events = []
    for e in events_raw:
        fn = EVENT_TEXT.get(e["event_type"])
        events.append(dict(t=iso_to_min(e["timestamp"]), type=e["event_type"],
                           text=fn(e) if fn else e["event_type"]))
    events.sort(key=lambda e: e["t"])
    orders_out = {oid: dict(id=oid, site=o["site_id"], planned=int(o["requested_start_min"]) if "requested_start_min" in o
                            else hhmm_to_min(o["requested_start"][11:]), actual=truth[oid],
                            trips=[]) for oid, o in orders.items()}
    trips_out = {}
    for t in trips:
        oid = t["order_id"]
        arr = hhmm_to_min(t["planned_arrival"][11:])
        trips_out[t["trip_id"]] = dict(id=t["trip_id"], order=oid, site=t["site_id"], seq=int(t["seq"]),
                                       vol=float(t["volume_m3"]), planned_arrival=arr)
        orders_out[oid]["trips"].append(t["trip_id"])
    for o in orders_out.values():
        o["trips"].sort(key=lambda tid: trips_out[tid]["seq"])
    return dict(orders=orders_out, trips=trips_out, events=events)


def kpi_timeline(log, trips_meta, orders_meta):
    """Event-attributed running totals; sums equal kpi.py at day end."""
    events = []  # (t, dict of deltas)
    by_order = {}
    for tid, lg in log.items():
        if "unload_end" not in lg:
            continue
        events.append((lg["unload_start"], dict(wait=lg["unload_start"] - lg["arrive"])))
        events.append((lg["unload_end"], dict(delivered=1, vol=trips_meta[tid]["vol"])))
        by_order.setdefault(trips_meta[tid]["order"], []).append(lg)
    for oid, lgs in by_order.items():
        lgs.sort(key=lambda l: l["unload_start"])
        ready = orders_meta[oid]["actual"]
        events.append((lgs[0]["unload_start"], dict(idle=max(0, lgs[0]["unload_start"] - ready))))
        for a, b in zip(lgs, lgs[1:]):
            events.append((b["unload_start"], dict(idle=b["unload_start"] - a["unload_end"])))
    merged = {}
    for t, delta in events:
        d = merged.setdefault(t, dict(wait=0, idle=0, delivered=0, vol=0.0))
        for k, v in delta.items():
            d[k] += v
    out, run = [], dict(wait=0, idle=0, delivered=0, vol=0.0)
    for t in sorted(merged):
        for k, v in merged[t].items():
            run[k] += v
        out.append([t, round(run["wait"], 1), round(run["idle"], 1), run["delivered"], round(run["vol"], 2)])
    return out


def build_policy(scenario, policy, trips_meta, orders_meta):
    fname = ITER / "logs" / f"{scenario}_{DAY}_{policy}.json"
    log = json.loads(fname.read_text(encoding="utf-8"))
    by_truck = {}
    for tid, lg in log.items():
        if "truck" in lg:
            by_truck.setdefault(lg["truck"], []).append((tid, lg))
    for trips in by_truck.values():
        trips.sort(key=lambda x: x[1]["load_start"])
    trucks_out = {}
    for truck, trips in by_truck.items():
        legs = []
        for tid, lg in trips:
            legs.append(dict(trip=tid, load_start=lg["load_start"], depart=lg["depart"], arrive=lg["arrive"],
                             unload_start=lg.get("unload_start"), unload_end=lg.get("unload_end"),
                             back=lg.get("back"), free=lg.get("free"), site=trips_meta[tid]["site"]))
        trucks_out[truck] = legs
    log_compact = {tid: {k: v for k, v in lg.items() if k != "truck"} | ({"truck": lg["truck"]} if "truck" in lg else {})
                   for tid, lg in log.items()}
    unserved = [tid for tid in trips_meta if "unload_end" not in log.get(tid, {})]
    return dict(trucks=trucks_out, kpi=kpi_timeline(log, trips_meta, orders_meta), unserved=unserved,
               trip_count=len(trips_meta), delivered=len(trips_meta) - len(unserved))


def add_results(bundle):
    """Day-9101 results (what the replay shows) and 10-day averages (the evidence)."""
    metrics = _rows(ITER / "metrics.csv")
    impact = [r for r in _rows(ROOT / "phase10_carbon_business/impact_runs.csv") if r["case"] == "value"]
    imp = {(r["seed"], r["scenario"], r["policy"]): r for r in impact}

    def row_out(m):
        i = imp[(m["seed"], m["scenario"], m["policy"])]
        d = {f: float(m[f]) for f in FIELDS}
        d.update({f: float(i[f]) for f in IMPACT_FIELDS})
        return d

    def mean(rows):
        return {k: round(sum(r[k] for r in rows) / len(rows), 3) for k in rows[0]}

    by = {}
    for m in metrics:
        if m["policy"] in POLICIES:
            by.setdefault((m["scenario"], m["policy"]), []).append((int(m["seed"]), row_out(m)))
    overall = {}
    for scenario in SCENARIOS:
        sc = bundle["scenarios"][scenario]
        info = SCENARIO_INFO[scenario]
        sc["about"], sc["watch"] = info
        for policy in POLICIES:
            rows = by[(scenario, policy)]
            day = [r for seed, r in rows if seed == DAY][0]
            sc["policies"][policy]["day_result"] = {k: round(v, 3) for k, v in day.items()}
            sc["policies"][policy]["avg10"] = mean([r for _, r in rows])
            sc["policies"][policy]["days"] = len(rows)
            overall.setdefault(policy, []).extend(r for _, r in rows)
    bundle["overall"] = {p: mean(v) for p, v in overall.items()}
    bundle["overall_runs"] = {p: len(v) for p, v in overall.items()}


def main():
    bundle = dict(day=DAY, scenarios={})
    check_rows = {r["scenario"] + "|" + r["policy"]: r for r in _rows(ITER / "metrics.csv") if int(r["seed"]) == DAY}
    for scenario in SCENARIOS:
        world = build_world(scenario)
        sc = build_scenario(scenario)
        policies_out = {}
        for policy in POLICIES:
            p = build_policy(scenario, policy, sc["trips"], sc["orders"])
            policies_out[policy] = p
            key = f"{scenario}|{policy}"
            real = check_rows[key]
            final = p["kpi"][-1] if p["kpi"] else [0, 0, 0, 0, 0]
            assert abs(final[1] - float(real["total_waiting_min"])) < 0.6, (key, final[1], real["total_waiting_min"])
            assert abs(final[2] - float(real["site_idle_min"])) < 0.6, (key, final[2], real["site_idle_min"])
            assert final[3] == int(real["delivered_trips"]), (key, final[3], real["delivered_trips"])
        bundle["scenarios"][scenario] = dict(label=LABELS[scenario], world=world, orders=sc["orders"],
                                             trips=sc["trips"], events=sc["events"], policies=policies_out)
    add_results(bundle)
    bundle["policy_labels"] = POLICY_LABEL
    bundle["scenario_order"] = SCENARIOS
    out = Path(__file__).resolve().parent / "sim_data.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK wrote", out, out.stat().st_size / 1024, "KB")


if __name__ == "__main__":
    main()
