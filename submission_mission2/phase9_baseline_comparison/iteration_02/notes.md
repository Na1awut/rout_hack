# Loop 7 · Iteration 02 — PASS

## Define

- **Hypothesis:** iteration 01 แพ้เพราะ dispatcher ไม่มี safety buffer ถ้าให้รถถึงไซต์เร็วขึ้นเล็กน้อย ช่องว่างระหว่างเทคอนกรีตจะลด และ C (AI) จะชนะ B (dynamic ไม่มี AI) ได้ตาม gate เดิม
- **ไม่เปลี่ยน:** score, ค่าปรับ 1000 นาที/เที่ยว, เกณฑ์ gate ทุกข้อ, โมเดล `site_ready_v3`, simulator, Core
- **เปลี่ยน:** เพิ่ม [buffered_dispatch.py](../../readymix/application/buffered_dispatch.py) (ไฟล์ใหม่ ไม่แตะ `dynamic_dispatch.py`) โดย B และ C ใช้กลไกเดียวกัน ต่างกันแค่ readiness input
- **ล็อกก่อนรัน:** [config.json](config.json) commit ก่อนรันใดๆ (commit `4849370`) · selection commit ก่อนเปิด eval days (commit `c5e4144`)

## ขั้นที่ 1 — เลือก buffer บน dev days 6001–6010 ([select_buffers.py](select_buffers.py))

Grid first ∈ {0,5,10,15,20} × next ∈ {0,5,10,15,20} × {B, C} × 9 scenario × 10 วัน = 4,500 run ผ่าน validator ทุก run

กฎเลือกที่ล็อกไว้: B เลือก score ต่ำสุด · C เลือก score ต่ำสุดในกลุ่มที่ on-time ≥ B − 0.02 และส่งไม่ได้ ≤ B

| Policy | first | next | dev score | dev on-time |
|---|---:|---:|---:|---:|
| B_dynamic_buffered | 0 | 10 | 2630.0 | 0.621 |
| C_ai_rolling_buffered | 5 | 15 | 2474.4 | 0.636 |

ไฟล์: [selection.json](selection.json), [dev_grid_summary.csv](dev_grid_summary.csv), [dev_metrics.csv](dev_metrics.csv)

## ขั้นที่ 2 — ประเมินบน fresh days 9101–9110 ([run_loop07.py](run_loop07.py))

10 วัน × 9 scenario × 5 policy = 450 run · valid ทุก run · predictor ไม่ fail เลย

| Gate (C_buffered เทียบ B_buffered) | ผล |
|---|---|
| all_execution_valid | PASS |
| no_predictor_failure | PASS |
| operational_gain_ci_positive | PASS: gain 218.2 นาที/วัน-scenario, CI95 [117.3, 346.2] |
| no_more_unserved | PASS: 0.633 เทียบ 0.711 |
| on_time_within_tolerance | PASS: 0.710 เทียบ 0.698 |

Paired day gains ทั้ง 10 วันเป็นบวก (11.9 ถึง 694.6) · C ชนะ B 74/90 คู่ · ไฟล์: [gates.json](gates.json), [metrics.csv](metrics.csv), [summary.csv](summary.csv), [scenario_summary.csv](scenario_summary.csv), [evaluation_lock.json](evaluation_lock.json), [run.log](run.log), [verification.log](verification.log)

ผลเต็มและข้อจำกัดอยู่ใน [PHASE9.md](../PHASE9.md)
