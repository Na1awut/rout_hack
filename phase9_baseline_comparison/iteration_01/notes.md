# Loop 7 · Iteration 01 — FAIL (เก็บไว้เป็นหลักฐาน ห้ามลบ)

วันประเมิน: day seeds 9001–9005 × 9 scenario × 3 policy = 135 run (world_seed 42)
รันครั้งแรกบน Windows ได้ 111/135 แล้วรันซ้ำครบบน Linux เมื่อ 2026-09-28 · 111 run ที่ซ้ำกันได้ `log_sha256` ตรงกันทุกตัว · hash ของโค้ด/โมเดล/config ตรงกับ `evaluation_lock.json` เดิม
(key ใน lock ยังเป็น path ก่อนย้ายโฟลเดอร์ `phase9_baseline_comparison/config.json`)

## ผล (ค่าเฉลี่ย 45 run ต่อ policy)

| Policy | รถรอ | ไซต์รอ | Score | ส่งไม่ได้ | On-time | น้ำมัน |
|---|---:|---:|---:|---:|---:|---:|
| A_static_planned | 458.6 | 1207.4 | **2821.5** | 1.16 | 0.594 | 837.3 |
| B_dynamic | 251.5 | 1552.4 | 3426.1 | 1.62 | 0.554 | 824.8 |
| C_ai_rolling | **99.1** | 1603.4 | 3347.0 | 1.64 | 0.522 | **817.3** |

| Gate (C เทียบ B) | ผล |
|---|---|
| all_execution_valid | PASS |
| no_predictor_failure | PASS |
| operational_gain_ci_positive | **FAIL**: gain เฉลี่ย 79.2 นาที, CI95 [-33.0, 170.0] |
| no_more_unserved | **FAIL**: 1.644 เทียบ 1.622 (ต่างกัน 1 เที่ยวใน S6) |
| on_time_within_tolerance | **FAIL**: 0.522 เทียบ 0.554 (ยอมให้ลดได้ไม่เกิน 0.02) |

## วินิจฉัย (ใช้ dev seeds 6001–6003 ไม่ใช้วันประเมิน)

- ถ้าไม่นับ S6 C ชนะ B ทุก scenario แต่ **ทั้ง B และ C แพ้ A** เพราะไซต์ต้องรอ
- แยกเวลาที่ไซต์รอ (idle) บน dev: ช่องว่างระหว่างเที่ยว A 290 / B 496 / C 534 นาที · ไซต์รอรถคันแรก A 332 / B 302 / C 356
- สาเหตุ: dispatcher ตั้งเวลาให้รถถึง**ตรงเวลาพอดี**กับเวลาที่คาดว่าไซต์พร้อม/คันก่อนเทเสร็จ ความคลาดของเวลาเดินทางหรือเวลาเทจึงกลายเป็นช่องว่างที่ไซต์รอ ส่วน C เล็งที่ค่ากลาง (median) ของ prediction ทำให้มาช้ากว่าไซต์พร้อมราวครึ่งหนึ่ง on-time จึงลด
- ตัว AI ไม่ได้ผิด แต่ dispatch objective ไม่มี safety buffer → ไปแก้ต่อใน iteration 02
