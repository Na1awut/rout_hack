# PourReady: AI and Optimization for Ready-Mix Concrete Dispatch

PourReady predicts when a construction site will really be ready, then decides which truck to release and when. It is built on a benchmarked CVRP solver and was developed for a route optimization hackathon.

> **All operating data is simulated.** The results show that the method works in a simulated world. They are not measurements from a real company. Fuel, labor and CO₂ factors come from public references and should be re-verified before external use.

## The problem

Concrete has a limited working life, so it cannot be mixed in advance and held. Trucks often reach a site before it is ready and wait with the engine running. If they arrive late, pump and pour crews stand idle and interrupted pours risk cold joints.

Early simulation showed that truck routes barely vary, because each trip goes from the plant to one site and back. The decision with real impact is therefore **when to dispatch**, not which way to drive.

## How it works

1. **Solver:** CORE-CVRP v1.1 runs on PyVRP 0.14.0 and is locked by regression tests.
2. **Site readiness model:** a scikit-learn model predicts when each site will be ready.
3. **Rolling optimizer:** the plan is refreshed every 15 minutes or when new information arrives, with a small safety buffer so sites do not wait for trucks.
4. **Validation:** every plan is checked for physical feasibility and compared with baselines on days not used for tuning.

## Results

Evaluated in simulation on 10 fresh days across 9 scenarios:

| Compared with | Result |
|---|---|
| The same rolling planner without AI | 218 fewer wasted minutes per day (95% CI 117–346), better on all 10 days |
| A fixed plan | 35% less truck waiting, 3.4 points better on-time rate, about 1,030 THB per day lower measured cost, and about 1% less CO₂ |
| A fixed plan when demand exceeds fleet capacity | **AI loses.** The system warns how many extra trucks are needed instead |

The fixed-plan advantage holds when the high-demand scenario is excluded. With it included, the overall result is a tie. The main value is saved time, and CO₂ is a small side benefit.

Solver check on the Mission 2 benchmarks:

| Instance | Optimal | Solution | Gap |
|---|---:|---:|---:|
| A-n32-k5 | 784 | 784 | 0.00% |
| B-n31-k5 | 672 | 672 | 0.00% |
| P-n40-k5 | 458 | 458 | 0.00% |

Across 24 CVRPLIB instances (21–935 points), all runs were feasible, with an average gap of 0.73% and a maximum of 2.26%.

## Getting started

Python 3.11 is required. `pyvrp` and `scikit-learn` are pinned on purpose: the frozen solver and the saved model depend on those exact versions.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r readymix/requirements.txt
export OMP_NUM_THREADS=1

python -m pytest readymix/tests -q
streamlit run readymix/dashboard/app.py
```

To reproduce the main evaluations:

```bash
python phase9_baseline_comparison/iteration_02/run_loop07.py 4
python phase10_carbon_business/run_loop08.py
python phase12_stress_test/run_loop09.py 4
```

To view the project site without installing anything, open [`phase13_report/site/index.html`](phase13_report/site/index.html). The truck replay is in `live.html` in the same folder.

## Repository guide

| Path | Contents |
|---|---|
| [`readymix/`](readymix/) | Shared code: simulation, AI, application logic, dashboard and tests |
| `phase1_freeze/` to `phase5_weakness_fix/` | Solver freeze, benchmarks and fixes |
| `phase6_readymix_simulation/` to `phase8_dynamic_optimizer/` | Simulator, readiness model and optimizer |
| `phase9_baseline_comparison/` to `phase12_stress_test/` | Evaluation, impact, dashboard and stress tests |
| [`phase13_report/`](phase13_report/REPORT.md) | Full project report (Thai) and project site |
| [`submission_mission2/`](submission_mission2/README.md) | Self-contained competition package (Thai) |
| `_archive/` | Earlier work kept for reference |

See [`STATUS.md`](STATUS.md) for per-phase results and [`PLAN.md`](PLAN.md) for the roadmap (both Thai).

## Known limitations

- The model uses one plant, identical trucks and one site per trip.
- There is no dedicated mode for days when demand exceeds fleet capacity.
- Cost figures cover only part of the real cost, and CO₂ excludes concrete production.
- On Linux, solver routes match the locked snapshot but `freeze_id` differs, so this still needs confirmation on the original Windows machine.
