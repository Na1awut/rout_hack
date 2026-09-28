"""Same probe, but with the CPU deliberately busy -- simulates the judges
re-running our code on a slower / shared machine."""
import multiprocessing as mp
import os
from time_vs_work_stop import run, BENCH


def burn():
    while True:
        pass


if __name__ == "__main__":
    hogs = [mp.Process(target=burn, daemon=True) for _ in range(os.cpu_count() * 2)]
    for h in hogs:
        h.start()
    path = f"{BENCH}\\P-n40-k5.vrp"
    for label, kw in [("time 1500ms (loaded)", dict(time_ms=1500)),
                      ("solution_limit 2000 (loaded)", dict(sol_limit=2000))]:
        res = [run(path, 5, **kw) for _ in range(3)]
        print(f"P-n40-k5 {label:30s} costs={[c for c,_,_ in res]} "
              f"distinct_routesets={len({f for _,f,_ in res})} "
              f"time={min(t for *_,t in res):.2f}-{max(t for *_,t in res):.2f}s")
    for h in hogs:
        h.terminate()
