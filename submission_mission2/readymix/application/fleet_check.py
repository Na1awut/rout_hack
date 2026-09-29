# fleet_check.py -- before the day: is the fleet big enough for the orders?
"""Planning-time check from master + order files only (no truth, no events).

A quick forecast of the day assuming every site is ready on time, typical
traffic and the estimated unload times: trips in planned-arrival order take
the earliest-free truck and loading bay, never load before the plant opens
and never after it closes, and one truck unloads at a time per order.

  INFEASIBLE  the forecast already leaves trips unloaded at closing time;
              extra_trucks = fewest added trucks (on shift from opening)
              that bring forecast unserved trips to zero
  AT_RISK     every trip fits, but more trips are late (> 15 min after plan)
              than with an unlimited fleet -- i.e. lateness caused by trucks;
              extra_trucks = fewest added trucks that remove that part
  OK          otherwise. Lateness that more trucks cannot fix (loading bays,
              an order booked faster than one truck can unload) is reported
              as structural_late, not blamed on the fleet

No tuned threshold. Real delays and breakdowns are unknown at planning time,
so OK is not a promise; the check is a floor on trouble, not a ceiling.
"""

import heapq

from readymix.simulation.dataset import load_plan

LATE_MIN = 15          # same tolerance as kpi.ON_TIME_TOLERANCE_MIN
MAX_EXTRA = 60


def _forecast(p, starts):
    pid = p.plant["plant_id"]
    if not starts:
        return len(p.trips), 0
    trucks = [(s, i) for i, s in enumerate(sorted(starts))]
    heapq.heapify(trucks)
    bays = [p.open_min] * p.bays
    site_free = {}
    unserved = late = 0
    for t in sorted(p.trips, key=lambda x: (x["planned_arrival_min"], x["trip_id"])):
        arr_plan = t["planned_arrival_min"]
        out = p.typical_travel(pid, t["site_id"], max(p.open_min, arr_plan - 60))
        want = arr_plan - out - p.load_min
        free, i = heapq.heappop(trucks)
        bay = min(range(len(bays)), key=lambda b: bays[b])
        start = max(want, free, bays[bay], p.open_min)
        if start >= p.close_min:
            unserved += 1
            heapq.heappush(trucks, (free, i))
            continue
        bays[bay] = start + p.load_min
        arrive = start + p.load_min + p.typical_travel(pid, t["site_id"], start)
        unload_start = max(arrive, site_free.get(t["order_id"], 0), p.orders[t["order_id"]]["requested_start_min"])
        unload_end = unload_start + float(p.orders[t["order_id"]]["estimated_unload_min"])
        site_free[t["order_id"]] = unload_end
        late += unload_start > arr_plan + LATE_MIN
        back = unload_end + p.typical_travel(pid, t["site_id"], int(unload_end))
        heapq.heappush(trucks, (back + p.wash_min, i))
    return unserved, late


def check_fleet(root) -> dict:
    p = load_plan(root)
    if not p.trips:
        return dict(status="NO_ORDERS", extra_trucks=0, trips=0, trucks=len(p.vehicles),
                    forecast_unserved=0, forecast_late=0, message="ไม่มี order วันนี้")
    starts = [max(p.open_min, v["available_from_min"]) for v in p.vehicles if v["available_from_min"] < p.close_min]
    unserved, late = _forecast(p, starts)
    out = dict(trips=len(p.trips), trucks=len(starts), forecast_unserved=unserved, forecast_late=late)

    _, floor_late = _forecast(p, starts + [p.open_min] * MAX_EXTRA)
    out["structural_late"] = floor_late

    def fewest(ok):
        for k in range(1, MAX_EXTRA + 1):
            if ok(*_forecast(p, starts + [p.open_min] * k)):
                return k
        return None

    if unserved:
        k = fewest(lambda u, l: u == 0)
        msg = (f"คาดว่าส่งไม่ทัน {unserved} เที่ยว ต้องเพิ่มรถอีก {k} คัน" if k is not None
               else f"คาดว่าส่งไม่ทัน {unserved} เที่ยว เพิ่มรถ {MAX_EXTRA} คันก็ยังไม่พอ (ติดที่ loading bay หรือเวลาทำการ)")
        return dict(out, status="INFEASIBLE", extra_trucks=k, message=msg)
    if late > floor_late:
        k = fewest(lambda u, l: u == 0 and l <= floor_late)
        return dict(out, status="AT_RISK", extra_trucks=k,
                    message=f"ส่งครบ แต่มี {late - floor_late} เที่ยวที่คาดว่าช้าเพราะรถไม่พอ เพิ่มรถอีก {k} คันจะแก้ได้")
    return dict(out, status="OK", extra_trucks=0,
                message="รถพอตามแผน" + (f" (มี {floor_late} เที่ยวที่ช้าเพราะแผนลูกค้า/bay ไม่ใช่เพราะรถ)" if floor_late else ""))
