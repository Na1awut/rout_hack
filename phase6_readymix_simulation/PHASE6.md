# Phase 6 — Ready-Mix Problem & Simulation ✅

สถานะ **PASS** (2026-09-28) · Loop 0, 1, 2 ผ่านทุก gate · CORE-CVRP v1.1 freeze_id `bf63a542f2de` ไม่ได้แก้ · dataset generator `loop01-v2`

ทำงานตาม [loop.md](../loop.md) (Define → Build → Test → Measure → Compare → Gate → Freeze) และ spec [skill.md](../skill.md) โค้ดที่ทุก phase ใช้ร่วมกันอยู่ใน [readymix/](../readymix/) ส่วนการทดลองและผลของ phase นี้อยู่ในโฟลเดอร์นี้

## สรุปสั้น

Phase 6 สร้าง "โลกจำลอง" ของธุรกิจคอนกรีตผสมเสร็จ ที่สร้างซ้ำได้ ตรวจสอบได้ และ Core ที่ freeze ไว้รับได้ จากนั้นจำลองวันทำงานทีละนาทีภายใต้ระบบที่ยังไม่มี AI เพื่อเก็บ KPI baseline ไว้ให้ Phase 7–9 เทียบ

| Loop | คำถาม | ผล |
|---|---|---|
| [0 Regression Lock](loop_00_regression_lock/notes.md) | benchmark mode ยังได้ผลเดิมไหม | ✅ A/B/P-n40/P-n19 Gap 0.00% route ตรงกับ snapshot |
| [1 Simulation](loop_01_simulation/notes.md) | สร้างวัน Ready-Mix ตาม schema ของ skill.md ที่สร้างซ้ำได้และ Core รับได้ไหม | ✅ 9 scenario ผ่าน validator สร้างซ้ำได้ byte เดิม Core ตอบตรงค่าที่คำนวณด้วยมือ |
| [2 Non-AI Baseline](loop_02_baseline/notes.md) | ถ้าไม่มี AI KPI เป็นเท่าไร | ✅ baseline A (แผน static) และ R (กฎตอบสนอง) บน 9 scenario + 5 seed |

Test ทั้งหมด: `python -m pytest readymix/tests` → **38 passed**

---

## ข้อค้นพบหลัก 3 ข้อ

### 1. ใน V1 ระยะทางแทบลดไม่ได้ การตัดสินใจจริงคือเวลาและลำดับ (Loop 1)

รถหนึ่งคันส่งให้ไซต์เดียวต่อเที่ยวแล้วกลับ plant และทุกเที่ยวใหญ่เกินครึ่งถัง จึงรวมสองเที่ยวในรถคันเดียวไม่ได้ CVRP แบบดูแค่ capacity จึงมีคำตอบได้แบบเดียว Core ตอบ 21,486 หน่วย ซึ่ง**เท่ากับ Σ 2·d(plant, site) ที่คำนวณด้วยมือพอดีทุก scenario** ระยะทางเปลี่ยนได้ก็ต่อเมื่อเปลี่ยนโครงสร้างปัญหา เช่น มีหลาย plant หรือยกเลิกเที่ยว

### 2. ถ้าไม่มีการทำนาย ต้องเลือกระหว่างรถรอกับไซต์รอ (Loop 2)

| S0 ปกติ, ค่าเฉลี่ย 5 seed | รถรอที่ไซต์ | ไซต์ว่าง | on-time |
|---|---:|---:|---:|
| A แผนที่ล็อกไว้เมื่อคืน | 451 นาที | 421 นาที | 0.799 |
| R กฎตอบสนอง ไม่มีการทำนาย | **288** | 541 | 0.812 |

R ลดเวลารถรอได้ 26–61% ทุก scenario แต่เวลาไซต์ว่างเพิ่มขึ้น 11–102% ทุก scenario **ถ้าทำนายเวลาไซต์พร้อมได้แม่น น่าจะลดได้ทั้งสองค่าพร้อมกัน** นี่คือสมมติฐานหลักที่ Phase 7–9 ต้องพิสูจน์

### 3. CO₂ ที่ลดได้จากการลดเวลารอน่าจะน้อย (Loop 2)

ด้วยอัตราน้ำมันตอนจอดรอที่ ASSUMED ไว้ น้ำมันจากการจอดรอคิดเป็นแค่ 0.4–4.7% ของน้ำมันทั้งหมด R ลดเวลารอได้ 180 นาทีแต่ลดน้ำมันได้แค่ 1.9% คุณค่าหลักจึงน่าจะอยู่ที่ **service** (ไซต์ว่าง, ช่องว่างระหว่างเที่ยว, on-time) และชั่วโมงรถ มากกว่า CO₂ **story ของสไลด์ควรปรับตามนี้** เว้นแต่ Loop 8 จะพบแหล่งข้อมูลที่บอกว่าอัตราน้ำมันตอนจอดสูงกว่านี้มาก

---

## ระบบที่สร้าง

```text
readymix/config/simulation.yaml, scenarios.yaml      ค่าตั้งทั้งหมด (SIMULATED / ASSUMED)
        │
        ▼
simulation/world → disruption_generator → traffic_simulator → site_simulator
        │   (random stream แยกตาม entity: seed เดียวกัน = โลกฐานเดียวกันทุก scenario)
        ▼
data/simulation/<scenario>_seed<N>/  + manifest.json (sha256, causality)  + data_dictionary.csv
        │
        ├──► application/data_validator         ตรวจ dataset อิสระจากตัวสร้าง
        ├──► application/capacity_projection  → CORE-CVRP v1.1 (frozen, ผ่าน core/frozen_core.py)
        └──► simulation/executor ◄── application/dispatch_policies (A, R)
                    │   Observation: policy เห็นเฉพาะข้อมูลที่เกิดขึ้นแล้ว
                    ▼
             application/execution_validator   ตรวจว่าวันที่จำลองเป็นไปได้ทางกายภาพ
             application/kpi                   KPI ตาม skill.md §18
```

**กติกาที่ phase ต่อไปต้องรักษา**
- **แบ่งการเข้าถึงข้อมูลเป็น 3 ระดับ:** `master/` กับ `orders/` รู้ล่วงหน้า · `runtime/` อ่านได้เฉพาะถึงเวลาปัจจุบัน · `ground_truth/` ใช้เป็น label เท่านั้น ห้ามใช้ตอนตัดสินใจ
- **ทุก field มี source_type:** Phase 6 ไม่มีค่าไหนเป็น REAL หรือ PUBLIC_SOURCE ค่า ASSUMED ต้องหาแหล่งอ้างอิงมาใส่ก่อนใช้ทำ claim
- **ทุกครั้งก่อนปิด loop** ต้องรัน `phase6_readymix_simulation/loop_00_regression_lock/regression_lock.py` และ pytest

## สิ่งที่แก้ระหว่าง phase

| เรื่อง | เดิม | ใหม่ | เหตุผล |
|---|---|---|---|
| ข้อมูลเวลาเดินทางของผู้วางแผน | ใช้ได้แค่ `traffic.csv` (รวมอนาคต) | เพิ่ม `master/travel_profile.csv` + กติกา causality | แผนที่วางล่วงหน้าต้องไม่รู้ traffic spike ในอนาคต |
| ปริมาตร order | lognormal 2.5, เริ่ม 07:00–14:00 | 2.2, 07:00–15:00 | ภาระเฉลี่ย 0.81 ทำให้ช่วงพีคล้น แผน A ตรงเวลาแค่ 35% ในวันปกติ |
| ช่วงภาระที่ยอมรับ | [0.60, 0.95] | [0.50, 0.85] | เป็นหลักฐานจาก Loop 2 ข้างบน |

## ข้อที่ต้องระวังก่อนนำไปพูด

- ทุกตัวเลขมาจาก**ข้อมูลจำลอง** ไม่ใช่ข้อมูลจริงของบริษัทใด
- simulator เป็นตัวกำหนดความสัมพันธ์ที่ AI ใน Phase 7 จะเรียนรู้ ความแม่นที่วัดได้จึงพิสูจน์แค่ว่า pipeline ทำงาน ไม่ได้พิสูจน์ความแม่นในโลกจริง
- ข้อ 2 ข้างบนคือ**สมมติฐาน** ยังไม่ใช่ผลที่พิสูจน์แล้ว
- อย่าพูดว่า "วันปกติตรงเวลา 90%" ค่านั้นมาจาก seed 42 seed เดียว ค่าเฉลี่ยข้าม 5 seed คือ 0.80
- skill.md §29 เขียน "100–300 trips/day" สำหรับรถ 15 คัน ซึ่งเป็นไปไม่ได้ ฝูงรถรับได้ราว 95 เที่ยวเมื่อวิ่งเต็ม 100% ตอนนี้ S0 มี 63 เที่ยว

## โครงสร้างไฟล์

```text
phase6_readymix_simulation/
├── PHASE6.md
├── loop_00_regression_lock/   regression_lock.py, snapshot.json, config.yaml, metrics.csv, notes.md
├── loop_01_simulation/        run_loop01.py, config.yaml, metrics.csv, notes.md
└── loop_02_baseline/          run_loop02.py, config.yaml, metrics.csv, seed_panel.csv, logs/, notes.md

readymix/                      โค้ดที่ทุก phase ใช้ร่วมกัน
├── core/frozen_core.py        ช่องทางเดียวที่เข้า CORE-CVRP v1.1 (อ่านอย่างเดียว)
├── config/                    simulation.yaml, scenarios.yaml
├── simulation/                common, world, disruption_generator, traffic_simulator, site_simulator,
│                              data_dictionary, build_dataset, stats, dataset, executor
├── application/               data_validator, capacity_projection, dispatch_policies, kpi, execution_validator
├── data/simulation/           dataset ทุก scenario × seed
└── tests/                     test_loop01_simulation.py, test_loop02_execution.py
```

## ส่งต่อ Phase 7 — AI Site Readiness (Loop 3–4)

**คำถามของ Loop 3:** AI ทำนายเวลาที่ไซต์พร้อมจริงได้ดีกว่าการใช้ planned time หรือค่าเฉลี่ยในอดีตหรือไม่

**สิ่งที่ต้องทำก่อน**
1. **สร้างสัญญาณก่อนเทคอนกรีต (§6):** ตอนนี้ความล่าช้าถูกกำหนดจาก trait ที่ซ่อนอยู่และจาก event เท่านั้น ยังไม่มีสัญญาณที่ AI สังเกตได้ ต้องเพิ่ม `site_state` เช่น pump_status, crew_status และ delay_so_far โดยให้สัญญาณมี**ความสัมพันธ์กับสาเหตุแบบมี noise** ไม่ใช่ copy label ไปใส่ ถ้าไม่ระวังตรงนี้ AI จะดูแม่นเพราะข้อมูลรั่ว
2. **สร้างข้อมูลหลายวันสำหรับเทรน (§29):** ใช้หลาย seed เช่น 100 วัน และแยก seed ของ train/test ออกจากกัน
3. **Baseline ที่ต้องชนะ (§11):** planned time และ historical mean ของไซต์
4. **Loop 4:** วัด calibration ของ confidence และกำหนดจุด fallback (§31)

**Baseline ที่ Phase 7–9 ต้องเทียบ:** [loop_02_baseline/metrics.csv](loop_02_baseline/metrics.csv) และ [seed_panel.csv](loop_02_baseline/seed_panel.csv)
