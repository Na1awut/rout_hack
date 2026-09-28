# Loop 1 — Ready-Mix Simulation ✅ PASS

2026-09-28 · seed 42 · generator `loop01-v2` · core freeze_id `bf63a542f2de` (ไม่ได้แก้)

> **รอบที่ 2 (ระหว่าง Loop 2):** v2 เพิ่ม `master/travel_profile.csv` (เวลาเดินทางปกติที่ผู้วางแผนรู้ล่วงหน้า) และกติกา causality ใน manifest เพราะ `traffic.csv` คือเวลาเดินทางที่เกิดขึ้นจริง อ่านล่วงหน้าไม่ได้ พร้อมปรับ calibration ของ order (ปริมาตร lognormal 2.5 → 2.2, เวลาเริ่ม 07:00–14:00 → 07:00–15:00, ช่วงภาระที่ยอมรับ [0.60, 0.95] → [0.50, 0.85]) เพราะ Loop 2 พบว่าภาระเฉลี่ย 0.81 ทำให้ช่วงพีคล้นจนแผน static ตรงเวลาแค่ 35% ในวันปกติ ตัวเลขด้านล่างเป็นของ v2 ที่รัน gate ใหม่แล้ว PASS

## 1. Define

**คำถาม:** เราสร้างวันทำงาน Ready-Mix ตาม schema ของ skill.md ได้ไหม โดยต้องรันซ้ำได้ผลเดิม, Core ที่ freeze ไว้รับข้อมูลได้, และแต่ละ scenario เปลี่ยนโลกตามที่ชื่อบอกจริง

**Gate G1–G9** อยู่ใน [config.yaml](config.yaml)

## 2. Build Minimal

| ไฟล์ | หน้าที่ | skill.md |
|---|---|---|
| [config/simulation.yaml](../../readymix/config/simulation.yaml) | ค่าตั้งของโลกจำลอง (ทุกตัวเลขเป็น SIMULATED/ASSUMED) | §27 |
| [config/scenarios.yaml](../../readymix/config/scenarios.yaml) | 9 scenario S0–S8 | §30 |
| [simulation/world.py](../../readymix/simulation/world.py) | plant, sites, trucks, orders และการแบ่ง order เป็นเที่ยว | §2–5 |
| [simulation/disruption_generator.py](../../readymix/simulation/disruption_generator.py) | event 8 ชนิด พร้อมเวลาที่ dispatcher รู้ | §21 |
| [simulation/traffic_simulator.py](../../readymix/simulation/traffic_simulator.py) | เวลาเดินทางรายชั่วโมง = base × multiplier | §7 |
| [simulation/site_simulator.py](../../readymix/simulation/site_simulator.py) | ground truth: เวลาไซต์พร้อมจริง, เวลา unload จริง | §8, §10 |
| [simulation/data_dictionary.py](../../readymix/simulation/data_dictionary.py) | ป้ายแหล่งที่มาของทุก field | §28 |
| [application/data_validator.py](../../readymix/application/data_validator.py) | validator ที่อ่านไฟล์กลับจากดิสก์และแยกจากตัวสร้าง | — |
| [application/capacity_projection.py](../../readymix/application/capacity_projection.py) | แปลง dataset เข้า Core v1.1 | — |

**กติกาที่ออกแบบไว้**
- **สุ่มแยกตาม entity:** แต่ละ entity ใช้ random stream ของตัวเอง โดยใช้ key (seed, หน้าที่, entity) เพิ่ม event ก็ไม่ทำให้ค่าสุ่มของส่วนอื่นเลื่อน seed เดียวกันจึงได้ plant/รถ/order ชุดเดียวกันทุก scenario ยกเว้น S6 ที่ตั้งใจเพิ่ม demand ทำให้ Loop 7 เทียบระบบ A/B/C บน demand ชุดเดียวกันได้
- **ความน่าเชื่อถือจริงของไซต์ถูกซ่อน:** แต่ละไซต์มีระดับ good/average/poor อยู่แค่ใน `ground_truth/` ส่วน sites.csv มีแค่ `historical_delay_mean/std` ซึ่งคำนวณจากการเทคอนกรีตในอดีต 60 ครั้งที่สุ่มขึ้นมา เหมือนข้อมูลที่บริษัทมีจริง คือบอกแนวโน้มได้แต่ไม่ใช่ความจริง
- **แยกข้อมูลตอนตัดสินใจออกจาก label:** `manifest.json` ระบุว่าไฟล์ไหนใช้ตัดสินใจได้ ไฟล์ไหนเป็น label ส่วนตัวแปลงเข้า Core ไม่อ่าน `ground_truth/` เลย และมี test ยืนยันว่าลบโฟลเดอร์นั้นทิ้งแล้วยังทำงานได้
- **เวลาของ event คือเวลาที่ dispatcher รู้** ไม่ใช่เวลาที่ผลเกิด เช่น SITE_DELAY จะแจ้งล่วงหน้า 30–90 นาทีก่อนเวลาพร้อมตามแผน ซึ่ง Loop 6 ต้องใช้

## 3–4. Test — `python -m pytest readymix/tests` → **27 passed**

- **การแบ่งเที่ยว:** ทดสอบทุกปริมาตร 4–80 m³ (ขั้น 0.5) ผลรวมต้องเท่ากับ order ทุกเที่ยวต้อง ≤ 6 m³ และ **> 3 m³ (เกินครึ่งถังเสมอ)** และมีกรณีขอบคือ 4, 6, 6.5, 12, 12.5
- **ทำซ้ำได้:** seed เดิมได้ไฟล์ byte เดิม, seed อื่นได้โลกคนละใบ, ทุก scenario ใช้โลกฐานเดียวกัน, ชื่อ scenario ที่ไม่มีอยู่ต้องถูกปฏิเสธ
- **ความหมายของ scenario:** จำนวน event ตรงกับนิยาม, PUMP_FAILURE เกิดเฉพาะไซต์ที่มีปั๊ม, event ใน S8 ขัดกับประวัติของไซต์จริง, SITE_DELAY บวก delay ให้เฉพาะ order ที่โดนเท่านั้น
- **Failure case (ฝังข้อผิดพลาด 11 แบบ):** แก้ไฟล์โดยไม่อัปเดต hash, FK ของไซต์ผิด, เที่ยวเกินความจุ, เที่ยวหาย, ช่อง traffic หาย, predicted ≠ base × mult, ความจุรถไม่เท่ากัน, status ผิด, คอลัมน์ที่ไม่มีใน dictionary, source_type ผิด และ label ที่ขัดกันเอง **validator จับได้ครบทุกกรณี**

## 5. Measure — [metrics.csv](metrics.csv)

| Scenario | เที่ยว | ภาระฝูงรถ | delay เฉลี่ย | traffic 7–18 น. | event | Core | ระยะทาง |
|---|---:|---:|---:|---:|---:|---|---:|
| S0 Normal | 63 | 0.641 | 7.7 นาที | ×1.33 | 0 | ✅ | 2,149 km |
| S1 Light traffic | 63 | 0.598 | 7.7 | ×1.17 | 0 | ✅ | 2,149 |
| S2 Peak traffic | 63 | 0.731 | 7.7 | ×1.65 | 2 | ✅ | 2,149 |
| S3 Site delay | 63 | 0.641 | 9.1 | ×1.33 | 1 | ✅ | 2,149 |
| S4 Multi site delay | 63 | 0.641 | 11.6 | ×1.33 | 3 | ✅ | 2,149 |
| S5 Pump failure | 63 | 0.641 | 9.9 | ×1.33 | 1 | ✅ | 2,149 |
| S6 High demand | 94 | **0.963** | 7.0 | ×1.33 | 0 | ✅ | 3,265 |
| S7 Mixed | 63 | 0.727 | 23.4 | ×1.61 | 7 | ✅ | 2,149 |
| S8 AI prediction error | 63 | 0.641 | 6.6 | ×1.33 | 4 | ✅ | 2,149 |

"ภาระฝูงรถ" = นาที-รถที่แผนต้องใช้ ÷ นาที-รถที่มี โดยยังไม่นับเวลารอ ค่านี้จึงเป็นขอบล่าง S6 ที่ได้ 0.96 แปลว่าฝูงรถแทบไม่มีที่ว่างเหลือ และเมื่อรวมช่วงพีคจะทำตามแผนไม่ทัน ซึ่งเป็นความตั้งใจของ scenario นี้ (Loop 2 วัดได้ว่าแผน static ตรงเวลาแค่ 21%)

## 6. Compare

Loop นี้ยังไม่มี baseline เดิมให้เทียบ จึงเทียบกับขนาดที่ skill.md §29 แนะนำแทน (1 plant, 10 sites, 15 trucks, 30 orders) ซึ่งตรงกันทุกค่า แต่ §29 ยังเขียนว่า "100–300 trips/day" **รถ 15 คันรับ 300 เที่ยวต่อวันไม่ไหว** ที่ระยะไซต์ 3–18 km รอบรถหนึ่งเที่ยวใช้ราว 90 นาที ฝูงรถจึงรับได้ประมาณ 95 เที่ยวต่อวันเมื่อวิ่งเต็ม 100% ตอนนี้ S0 มี 63 เที่ยว

## 7. Decision Gate — **PASS → Freeze** (G1–G7 จาก `run_loop01.py` · G8 Loop 0 PASS · G9 pytest 27/27)

## ข้อค้นพบที่ต้องส่งต่อ

**1. ถ้าดูแค่ capacity ระยะทางถูกกำหนดตายตัว**
รถ Ready-Mix หนึ่งคันส่งให้ไซต์เดียวต่อเที่ยวแล้วกลับ plant และทุกเที่ยวใหญ่เกินครึ่งถัง จึงรวมสองเที่ยวในรถคันเดียวไม่ได้ ผลคือ CVRP มีคำตอบได้แบบเดียว Core ตอบ 21,486 หน่วย (S0) ซึ่ง**เท่ากับ Σ 2·d(plant, site) ที่คำนวณด้วยมือพอดีทั้ง 9 scenario** ระยะทางจึงเท่ากับ 2,149 km ทุก scenario (ยกเว้น S6 ที่ order เปลี่ยน)
- ระยะทางเปลี่ยนได้ก็ต่อเมื่อเปลี่ยนโครงสร้างปัญหา เช่น มีหลาย plant หรือยกเลิก/เปลี่ยนเส้นทางกลางทาง
- ดังนั้นใน Loop 5–7 **KPI หลักต้องเป็นเวลารถรอ, เวลาไซต์ว่าง, ช่องว่างระหว่างเที่ยว, on-time และน้ำมันตอนจอดรอ** ไม่ใช่ระยะทาง
- ตัวอย่างใน skill.md §19 ที่แสดงระยะทางลดจาก 520 เป็น 508 km จึงไม่น่าเกิดใน V1 ที่มี plant เดียว
- สิ่งที่ solver ต้องตัดสินจริงคือ รถคันไหน, ออกเมื่อไร, และลำดับเที่ยว ซึ่งตรงกับ §15

**2. ข้อจำกัดของ AI ที่เทรนบนข้อมูลนี้**
simulator เป็นตัวกำหนดความสัมพันธ์ที่ AI ใน Loop 3 จะเรียนรู้ ความแม่นที่วัดได้จึงพิสูจน์ได้แค่ว่า pipeline ทำงาน ไม่ได้พิสูจน์ความแม่นในโลกจริง ต้องพูดเรื่องนี้ตรงๆ บนเวที S8 มีไว้ทดสอบว่าระบบจะเป็นอย่างไรเมื่อ AI ผิด

**3. สิ่งที่ยังไม่มีใน Loop 1**
- `site_state.csv` (§6) ยังไม่มี เพราะ field อย่าง queue_length, current_truck_count, previous_unload_min ขึ้นกับว่ารถถูกจัดลงไปอย่างไร ต้องรอ execution simulator ของ Loop 2
- ชุดข้อมูลหลายวันสำหรับเทรน AI (§29 แนะนำ 100 วัน) ทำได้ทันทีด้วยการสร้างหลาย seed จะทำใน Loop 3
- DEMAND_CHANGE มีอยู่แค่ใน ground truth (`final_volume_m3`) แผนเริ่มวันยังใช้ปริมาตรเดิม
- ค่า ASSUMED ทั้งหมด (ความจุ 6 m³, เวลาโหลด, น้ำมัน) ยังไม่มีแหล่งอ้างอิง ห้ามใช้ทำ claim จนกว่า Loop 8 จะหาแหล่งมาใส่

## 8. Version Snapshot

- ไม่มี git จึงใช้ `manifest.json` ของแต่ละ dataset แทน tag โดยเก็บ seed, scenario, SHA-256 ของ config ทั้งสองไฟล์ และ SHA-256 ของทุกไฟล์ข้อมูล
- dataset อยู่ที่ `readymix/data/simulation/<scenario>_seed42/` (รวม 9 ชุด ~0.5 MB)

```text
python -m readymix.simulation.build_dataset --scenario all          # สร้างใหม่
python phase6_readymix_simulation/loop_01_simulation/run_loop01.py        # gate G1-G7
python -m pytest readymix/tests                                     # G9
python phase6_readymix_simulation/loop_00_regression_lock/regression_lock.py   # G8
```
