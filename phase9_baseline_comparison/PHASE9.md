# Phase 9 — Baseline Comparison (Loop 7: AI vs No-AI) ✅

สถานะ **PASS** (2026-09-28) · iteration 01 FAIL (เก็บไว้ครบ) → วินิจฉัย → iteration 02 PASS บน fresh days ที่ไม่เคยใช้ · Core ไม่ได้แก้ · โมเดล `site_ready_v3` ไม่ได้ train ใหม่

> **คำถามของ Loop 7:** ระบบ AI ลดเวลารอ/ไซต์ว่างได้มากกว่าระบบ dynamic ที่ไม่มี AI จริงไหม (ใน scenario เดียวกัน วันเดียวกัน)

## สรุปสั้น

| | ผล |
|---|---|
| Gate หลัก (C เทียบ B) | ✅ ผ่าน 5/5 · C ดีกว่า B **218 นาทีต่อวัน-scenario** CI95 [117, 346] · ดีกว่าทั้ง 10 วัน |
| เทียบกับแผน static เดิม (A) | ไม่นับ S6 C ดีกว่า A **15.2%** (CI95 ของ gain [104, 239] นาที) · ถ้านับ S6 ด้วย **เสมอกัน** (1834.7 เทียบ 1839.0, CI [-155, 148]) |
| จุดที่ยังแพ้ | S6 demand เกินฝูงรถ: A ส่งได้มากกว่าและ score ดีกว่า |
| ข้อมูล | SIMULATED ทั้งหมด · world_seed 42 · fresh day seeds 9101–9110 |

## ระบบที่เทียบกัน

| Policy | คืออะไร | ใช้ใน gate |
|---|---|---|
| A_static_planned | แผนที่ล็อกไว้เมื่อคืน ปล่อยรถตามเวลาที่วางแผน ไม่ปรับระหว่างวัน (แทน "manual / current planning") | อ้างอิง |
| B_dynamic | Phase 8 dispatcher ใช้เวลาตามแผน + ประกาศล่าสุด ไม่มี AI | อ้างอิง (iteration 01) |
| C_ai_rolling | เหมือน B แต่ใช้ AI ทำนายเวลาไซต์พร้อม ทุก 15 นาที | อ้างอิง (iteration 01) |
| **B_dynamic_buffered** | B + safety buffer (0, 10 นาที) | ✅ baseline ของ gate |
| **C_ai_rolling_buffered** | C + safety buffer (5, 15 นาที) | ✅ ระบบที่ทดสอบ |

**เรื่อง Nearest Neighbor และ Standard CVRP ใน PLAN.md:** ใน V1 รถหนึ่งเที่ยวไปได้ไซต์เดียวแล้วต้องกลับ plant ทุกวิธีจึงได้ route เดียวกัน (Phase 6 พิสูจน์แล้วว่า Core ตอบ Σ 2·d(plant, site) ตรงกับที่คำนวณด้วยมือ) ระยะทางใน `metrics.csv` ต่างกันเฉพาะเพราะจำนวนเที่ยวที่ส่งไม่ได้ต่างกัน การเทียบจึงเป็นเรื่อง **เวลาปล่อยรถ** ระหว่าง A/B/C

## ผล fresh days 9101–9110 (ค่าเฉลี่ย 90 run ต่อ policy)

| Policy | รถรอ (นาที) | ไซต์ว่าง (นาที) | **Score** | ส่งไม่ได้ (เที่ยว) | On-time | น้ำมัน (ลิตร) | ช่องว่าง >30 นาที | Solver (ms/วัน) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_static_planned | 430.9 | 941.4 | 1839.0 | **0.47** | 0.676 | 799.2 | **4.24** | 2 |
| B_dynamic | 255.3 | 1157.3 | 2190.3 | 0.78 | 0.664 | 787.6 | 8.31 | 24 |
| C_ai_rolling | **103.9** | 1172.1 | 2053.8 | 0.78 | 0.619 | **780.0** | 7.59 | 2293 |
| B_dynamic_buffered | 336.4 | 1005.4 | 2052.9 | 0.71 | 0.698 | 792.1 | 5.43 | 23 |
| **C_ai_rolling_buffered** | 282.0 | **919.4** | **1834.7** | 0.63 | **0.710** | 790.2 | 4.64 | 2160 |

Score = รถรอ + ไซต์ว่าง + 1000 × เที่ยวที่ส่งไม่ได้ (หน่วยนาทีเทียบเท่า **ไม่ใช่ต้นทุนเงิน**) · ยิ่งต่ำยิ่งดี

### Score ราย scenario

| Scenario | A | B | C | B_buf | **C_buf** |
|---|---:|---:|---:|---:|---:|
| S0 ปกติ | 895 | 982 | 858 | 936 | **787** |
| S1 จราจรเบา | 897 | 907 | 781 | 881 | **721** |
| S2 จราจรติดหนัก | 1174 | 1396 | 1213 | 1295 | **1086** |
| S3 ไซต์ delay | 967 | 971 | 884 | 940 | **839** |
| S4 หลายไซต์ delay | 1107 | 1031 | 934 | 985 | **865** |
| S5 ปั๊มเสีย | 1028 | 987 | 887 | 949 | **837** |
| S6 demand สูง (เกินฝูงรถ) | **7269** | 10336 | 9952 | 9424 | 8637 |
| S7 disruption ผสม | 2071 | 2090 | 2032 | 2107 | **1858** |
| S8 AI ทายผิด | 1144 | 1014 | 943 | 959 | **883** |

C_buffered ดีที่สุดใน 8/9 scenario รวม S8 ที่ตั้งใจให้ AI ทายผิด

## เปรียบเทียบที่สำคัญ (paired ตามวัน, bootstrap 2000 ครั้ง)

| เทียบ | Score ที่ลดได้ต่อวัน-scenario | CI95 | หมายเหตุ |
|---|---:|---|---|
| **C_buf เทียบ B_buf (gate)** | **218.2** | [117.3, 346.2] | ผลของ AI เมื่อ dispatcher เหมือนกัน |
| C_buf เทียบ C (ผลของ buffer) | 219.1 | [75.4, 339.6] | buffer ช่วยจริง |
| C_buf เทียบ A ทุก scenario | 4.3 | [-155.1, 148.4] | เสมอ ไม่ควรอ้างว่าชนะ |
| C_buf เทียบ A ไม่นับ S6 | 175.9 | [103.8, 239.4] | ดีกว่า 15.2% |

เทียบกับ A (ทุก scenario): รถรอลดลง **34.6%** · ไซต์ว่างลดลง 2.3% · on-time +3.4 จุด · น้ำมันลดลง 1.1% · แต่ส่งไม่ได้เพิ่ม 0.17 เที่ยวต่อ run (มาจาก S6)

## เรื่องราวของ iteration

### Iteration 01 — FAIL ([notes](iteration_01/notes.md))

Day seeds 9001–5 ทำ 135 run: C ลดเวลารถรอได้ 61% เทียบกับ B แต่ gate ไม่ผ่าน 3 ข้อ คือ gain CI คร่อม 0, ส่งไม่ได้มากกว่า B 1 เที่ยว และ on-time ต่ำกว่า B 3.2 จุด **ทั้ง B และ C แพ้แผน static A** เพราะไซต์ว่างมากกว่า

วินิจฉัยบน dev seeds (ไม่ใช้วันประเมิน): dispatcher เล็งให้รถถึง**ตรงเวลาพอดี**กับเวลาที่คาดว่าไซต์พร้อม หรือเวลาที่คันก่อนเทเสร็จ พอเวลาเดินทางหรือเวลาเทคลาดไปนิดเดียวก็เกิดช่องว่าง (dev: ช่องว่าง A 290 / B 496 / C 534 นาที) C ยิ่งหนักเพราะเล็งที่ค่ากลางของ prediction จึงมาช้ากว่าไซต์พร้อมราวครึ่งหนึ่งของครั้ง

### Iteration 02 — PASS ([notes](iteration_02/notes.md))

เพิ่ม safety buffer ให้รถคันแรกและคันถัดไปของแต่ละ order ถึงเร็วขึ้นตามจำนวนนาทีที่กำหนด เลือก buffer บน dev days 6001–10 ด้วยกฎที่ commit ไว้ก่อนรัน แล้วเปิด fresh days 9101–10 **ครั้งเดียว** gate, score และโมเดลไม่เปลี่ยน

**Insight ที่ได้:** AI ที่ดีขึ้นอย่างเดียวไม่พอ ต้องให้ optimizer ใช้ prediction แบบเผื่อความไม่แน่นอนด้วย เมื่อมี buffer แล้ว C ใช้ buffer เล็ก (5/15 นาที) ก็ได้ on-time สูงกว่า B ที่ไม่มี AI เพราะรู้เวลาไซต์พร้อมแม่นกว่า

## ความน่าเชื่อถือ

- iteration 01 รันซ้ำบน Linux: 111 run ที่เคยรันบน Windows ได้ `log_sha256` ตรงกันทุกตัว · hash ของโค้ด/โมเดล/config ตรงกับ lock
- ไม่มีการเลือก policy บนวันประเมิน · seeds ที่เคยใช้แล้ว (1001–1120, 2001–2040, 3001–3020, 4001–4020, 7001–7040, 8001–8020, 9001–9005) ไม่ซ้ำกับ dev/eval
- `dynamic_dispatch.py` ไม่ได้แก้ (hash เดิม `63de6950…`) · หลักฐาน Phase 8 จึงยังรันซ้ำได้
- Tests: `python -m pytest readymix/tests` → **104 passed** (เพิ่ม 4 ข้อใน `test_loop07_buffered.py` รวมข้อที่ตรวจว่า buffer 0 ได้ log เหมือน `DynamicDispatch` ทุกตัว)
- **Core regression:** route, cost และ iterations ของ A/B/P-n40/P-n19 ตรง snapshot ทุกตัว (Gap 0.00%) แต่บน Linux checkout นี้ `freeze_id` คำนวณได้ `91a1a0dbb3bf` ไม่ใช่ `bf63a542f2de` ไฟล์ Core ไม่ถูกแก้ตั้งแต่ commit แรก ลอง CRLF ทั้งชุดแล้วก็ยังไม่ตรง **ต้องรัน `regression_lock.py` บนเครื่อง Windows เดิมเพื่อยืนยัน** ([verification.log](iteration_02/verification.log))

## ข้อจำกัด (ต้องพูดตรงๆ บนสไลด์)

- ข้อมูลทั้งหมดเป็น **SIMULATED** · plant เดียว · รถเหมือนกันทุกคัน · 1 เที่ยวต่อ 1 ไซต์
- C ไม่ได้ชนะแผน static แบบรวมทุก scenario: **เสมอ** · ชนะชัดเฉพาะเมื่อไม่นับ S6 (demand เกินฝูงรถ)
- S6: ระบบ dynamic ทั้งหมดส่งได้น้อยกว่า A → ถ้าไปต่อ ควรเพิ่มโหมด "เกินกำลัง" (ปล่อยรถล่วงหน้าเต็มที่/จัดลำดับ order) ใน Phase 12 Stress Test
- ค่า buffer จูนจาก simulator นี้ ถ้าใช้จริงต้องจูนใหม่จากข้อมูลจริง
- Score เป็น proxy (นาทีรถรอ = นาทีไซต์ว่าง) ยังไม่ใช่เงิน → Phase 10 แปลงเป็น THB / CO₂
- น้ำมันลดลงแค่ ~1% ตรงกับข้อค้นพบใน Phase 6 ว่าคุณค่าหลักอยู่ที่ service ไม่ใช่ CO₂
- CI มาจาก 10 วันอิสระ ถือเป็นการทดลองเชิงสำรวจ

## ไฟล์และคำสั่ง

```bash
export OMP_NUM_THREADS=1
python -m pytest readymix/tests -q --disable-warnings
python phase9_baseline_comparison/iteration_01/run_loop07.py          # 135 run, FAIL (ตั้งใจเก็บไว้)
python phase9_baseline_comparison/iteration_02/select_buffers.py 4    # dev 6001-6010 → selection.json
python phase9_baseline_comparison/iteration_02/run_loop07.py 4        # fresh 9101-9110 → gates.json
python phase6_readymix_simulation/loop_00_regression_lock/regression_lock.py
```

Environment ที่ใช้รัน iteration 02: Linux x86_64, Python 3.11.15, pyvrp 0.14.0, scikit-learn 1.9.0, numpy 2.4.6, pandas 3.0.6

## ส่งต่อ Phase 10

ใช้ `iteration_02/metrics.csv` เป็น data pack ของ `baseline_comparison.csv` แปลงรถรอ/ไซต์ว่าง/น้ำมันเป็น THB และ CO₂ (ยังต้องหาแหล่ง emission factor ที่อ้างอิงได้) โดยรายงาน S6 แยกไว้เสมอ
