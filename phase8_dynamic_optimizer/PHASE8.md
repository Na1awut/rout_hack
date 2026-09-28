# Phase 8 — Predictive Dynamic Optimizer (Loop 5–6) ✅

สถานะ **PASS** · gate ผ่าน 5/5 ([gates.json](gates.json)) · Core ไม่ได้แก้ · ใช้ `site_ready_v3` จาก Phase 7 โดยไม่ train ใหม่
รายงานนี้เขียนย้อนหลังเมื่อ 2026-09-28 จากหลักฐานในโฟลเดอร์นี้ และรันซ้ำบน Linux แล้วได้ **36/36 run ที่ log และ dataset ตรงกันทุก byte**

## คำถาม

| Loop | คำถาม (จาก [config.json](config.json)) |
|---|---|
| 5 Extended Optimizer | prediction เปลี่ยนเวลาปล่อยรถได้จริงไหม และการทำงานยังถูก constraint |
| 6 Rolling Re-optimization | ปรับแผนของเที่ยวที่ยังไม่ปล่อยได้ไหมเมื่อมีข้อมูลใหม่ โดยไม่แตะเที่ยวที่ปล่อยไปแล้ว |

## ระบบที่สร้าง

```text
readymix/application/extended_solver.py    DispatchJob + best_release (หาเวลาปล่อยที่ต้นทุน early/late ต่ำสุดแบบ exact บน grid 5 นาที)
                                           + solve_dispatch (แจก loading slot ตามความล่าช้าที่เลี่ยงได้ × priority)
readymix/application/dynamic_dispatch.py   DynamicDispatch: B (ไม่มี AI) และ C (AI) ใช้กลไกเดียวกัน ต่างกันแค่ readiness input
                                           C_ai_snapshot = ทำนายครั้งเดียว · C_ai_rolling = ทำนายใหม่ทุก 15 นาทีหรือเมื่อมี event ใหม่
```

- เที่ยวที่ปล่อยแล้วจะไม่กลับเข้ามาเป็นตัวเลือกอีก (lock) ส่วนเที่ยวที่ยังไม่ปล่อยวางแผนใหม่ได้ทุก step
- ถ้าไซต์โทรแจ้งว่าพร้อมแล้ว (`ready_call`) จะใช้ค่านั้นแทน prediction · ถ้า predictor error จะ fallback ไปใช้ planned + ประกาศ
- ถ้ารถคันก่อนถึงไซต์แล้วแต่ไซต์ยังไม่พร้อม จะหยุดส่งรถคันถัดไปของ order นั้นไว้ก่อน (hold)
- ไม่อ้างว่าเป็น global optimum: เลือกเวลาของแต่ละ job แบบ exact แล้วแจก slot ปัจจุบันแบบ greedy

## Gate (S0–S8, seed 42, 36 run)

| Gate | ผล |
|---|---|
| execution_valid | PASS ทุก run ผ่าน `execution_validator` |
| prediction_changes_decisions | PASS log ของ B ≠ C_snapshot |
| rolling_changes_decisions | PASS log ของ C_snapshot ≠ C_rolling |
| no_predictor_failures | PASS |
| normal_orders_served | PASS S0 ส่งครบทุกเที่ยว |

Tests `readymix/tests` 100 passed ([pytest.log](pytest.log)) · Core regression PASS ([core_regression.log](core_regression.log)) · reproducibility 4/4 ([reproducibility.json](reproducibility.json))

## KPI (ค่าเฉลี่ย 9 scenario, วันเดียว seed 42)

| Policy | รถรอ | ไซต์ว่าง | ส่งไม่ได้ | On-time | น้ำมัน | เรียก AI | ms/วัน |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_static_planned | 569.6 | **660.3** | 0.00 | **0.78** | 796.5 | 0 | 1 |
| B_dynamic | 326.0 | 919.0 | 0.11 | 0.73 | 783.5 | 0 | 16 |
| C_ai_snapshot | 291.8 | 955.8 | 0.00 | 0.71 | 782.0 | 31 | 317 |
| C_ai_rolling | **127.8** | 911.9 | 0.11 | 0.72 | **773.8** | 190 | 1706 |

ตัวอย่าง audit ([S3 C_rolling decisions](logs/S3_site_delay__C_ai_rolling_decisions.json)): 63 การปล่อยรถ มาจาก prediction ของ `site_ready_v3` 47 ครั้ง และจากการที่ไซต์โทรแจ้งว่าพร้อม 16 ครั้ง

## ข้อค้นพบ → ส่งต่อ Phase 9

- AI + rolling ลดเวลารถรอได้มาก (A 570 → C 128 นาที) และ decision เปลี่ยนตาม prediction จริง
- **แต่ไซต์ว่างเพิ่มขึ้นและ on-time ต่ำกว่า A** ตั้งแต่ Phase 8 แล้ว ตอนนั้นยังไม่ได้ gate ผลนี้เพราะ Phase 8 ถามแค่ว่า "decision เปลี่ยนและ valid" · ผลนี้เป็นสาเหตุที่ Phase 9 iteration 01 FAIL แล้วแก้ด้วย safety buffer ใน iteration 02 (ดู [PHASE9.md](../phase9_baseline_comparison/PHASE9.md))
- วันเดียว seed เดียว: ใช้ยืนยันกลไก ไม่ใช่หลักฐานเชิงสถิติ
- ข้อมูล SIMULATED ทั้งหมด

## คำสั่ง

```bash
export OMP_NUM_THREADS=1
python phase8_dynamic_optimizer/run_phase8.py
python -m pytest readymix/tests -q --disable-warnings
```
