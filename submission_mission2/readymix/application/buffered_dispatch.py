"""DynamicDispatch with arrival safety buffers (Loop 7 iteration 02).

Iteration 01 timed every load to arrive exactly at the expected ready time
(first load) or the projected end of the previous unload (later loads).
Any travel/unload variance then became a pour gap: site idle rose above the
static plan for both B and C. A buffer moves the arrival target earlier by a
fixed number of minutes, trading truck waiting for site idle.

B and C share this exact mechanism; the only difference stays the readiness
input. dynamic_dispatch.py is left untouched so Phase 8 evidence reproduces.
"""
from .dynamic_dispatch import DynamicDispatch
from .extended_solver import DispatchJob, solve_dispatch


class BufferedDispatch(DynamicDispatch):
    def __init__(self, predictor=None, first_buffer_min=0, next_buffer_min=0, **kwargs):
        super().__init__(predictor, **kwargs)
        if first_buffer_min < 0 or next_buffer_min < 0:
            raise ValueError("buffers must be non-negative")
        self.first_buffer, self.next_buffer = first_buffer_min, next_buffer_min
        self.name += "_buffered"

    def decide(self, obs):
        # Same as DynamicDispatch.decide except the two marked target lines.
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
            if end is None:
                target = ready - self.first_buffer                          # buffer: first load
            else:
                target = max(end + spacing - self.next_buffer, now)         # buffer: later loads
            job = DispatchJob(pending["trip_id"], target, lead, int(p.orders[oid].get("priority", 1)))
            jobs.append(job)
            info[job.trip_id] = source
        chosen, proposals = solve_dispatch(jobs, now, p.close_min, obs.loading_slots(), self.step,
                                            self.waiting_weight, self.late_weight)
        for row in proposals:
            if row["trip_id"] in chosen:
                self.audit.append(dict(t=now, source=info[row["trip_id"]], **row))
        return chosen
