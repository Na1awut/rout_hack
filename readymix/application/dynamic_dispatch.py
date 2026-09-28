"""Shared B/C dispatch scheduler. The only difference is readiness input.

B uses current announcements/planned time; C uses the frozen predictor.
Readiness calls, live traffic, resource slots, objective and locks are shared.
"""
from readymix.simulation.common import iso_to_min
from .dispatch_policies import ReactiveRule
from .extended_solver import DispatchJob, solve_dispatch


class DynamicDispatch(ReactiveRule):
    def __init__(self, predictor=None, rolling=True, refresh_min=15, step_min=5,
                 waiting_weight=1, late_weight=1):
        self.predictor, self.rolling = predictor, rolling
        self.refresh_min, self.step = refresh_min, step_min
        self.waiting_weight, self.late_weight = waiting_weight, late_weight
        self.name = "B_dynamic" if predictor is None else ("C_ai_rolling" if rolling else "C_ai_snapshot")

    def start(self, plan):
        super().start(plan)
        self.cache, self.audit = {}, []
        self.calls, self.failures = 0, 0

    def readiness(self, obs, oid, shift):
        order = self.plan.orders[oid]
        planned = order["requested_start_min"]
        if obs.site_reported_ready(oid):
            return obs.t, "ready_call"
        baseline = max(obs.t, planned + shift)
        if self.predictor is None:
            return baseline, "planned+announced"
        state = obs.site_state(oid)
        if state is None or obs.t < planned - 90:
            return baseline, "no_report"
        events = obs.events()
        signature = tuple(e.get("event_id", str(e)) for e in events if e.get("order_id") == oid)
        old = self.cache.get(oid)
        refresh = old is None or (self.rolling and (obs.t - old["t"] >= self.refresh_min or signature != old["events"]))
        if refresh:
            try:
                p = self.predictor.predict(state, self.plan.sites[order["site_id"]], order,
                                           events, obs.t, order["requested_start"][:10])
                from readymix.ai.predictor import validate_prediction
                errors = validate_prediction(p)
                if errors:
                    raise ValueError(str(errors))
                ready, source = iso_to_min(p["predicted_ready_time"]), p["model_version"]
                if p["fallback_used"]:
                    source += ":fallback"
                self.calls += 1
            except (ValueError, RuntimeError, KeyError, TypeError):
                ready, source = baseline, "predictor_failure:planned+announced"
                self.failures += 1
            self.cache[oid] = dict(t=obs.t, ready=ready, source=source, events=signature)
        value = self.cache[oid]
        return max(obs.t, value["ready"]), value["source"]

    def decide(self, obs):
        p, now = self.plan, obs.t
        if now < p.open_min or now >= p.close_min:
            return []
        shift = self._shift(obs)
        jobs, info = [], {}
        for oid, trips in sorted(self.by_order.items()):
            pending = next((tr for tr in trips if not obs.released(tr["trip_id"])), None)
            if pending is None:
                continue
            travel = obs.travel_now(p.plant["plant_id"], pending["site_id"])
            lead = p.load_min + travel
            ready, source = self.readiness(obs, oid, shift.get(oid, 0))
            # For subsequent trips follow the last committed load's projected
            # unload end; never send it to another order or alter its history.
            end = None
            hold = False
            unload = float(p.orders[oid]["estimated_unload_min"])
            for tr in trips:
                if not obs.released(tr["trip_id"]):
                    break
                lg = obs.trip(tr["trip_id"])
                if "unload_end" in lg:
                    end = lg["unload_end"]
                elif "unload_start" in lg:
                    end = max(now, lg["unload_start"] + unload)
                else:
                    arrival = (lg["arrive"] if "arrive" in lg else lg["depart"] + lg["travel_out"] if "depart" in lg
                               else lg.get("load_start", now) + lead)
                    hold |= "arrive" in lg and not obs.site_reported_ready(oid)
                    end = max(arrival, ready, end or 0) + unload
            if hold:
                continue
            spacing = max(0, float(p.orders[oid]["target_interval_min"]) - unload)
            target = ready if end is None else max(end + spacing, now)
            job = DispatchJob(pending["trip_id"], target, lead, int(p.orders[oid].get("priority", 1)))
            jobs.append(job)
            info[job.trip_id] = source
        chosen, proposals = solve_dispatch(jobs, now, p.close_min, obs.loading_slots(), self.step,
                                            self.waiting_weight, self.late_weight)
        for row in proposals:
            if row["trip_id"] in chosen:
                self.audit.append(dict(t=now, source=info[row["trip_id"]], **row))
        return chosen
