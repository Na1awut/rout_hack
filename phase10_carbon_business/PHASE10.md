# Phase 10 — Carbon + Business Impact (Loop 8) ✅

สถานะ **PASS** (2026-09-28) · gate ผ่าน 4/4 ([gates.json](gates.json)) · ไม่ได้รัน simulator ใหม่ ใช้ log 450 run ของ [Phase 9 iteration 02](../phase9_baseline_comparison/iteration_02/notes.md) ที่ล็อกไว้แล้ว

> **คำถาม:** การตัดสินใจที่ดีขึ้นใน Phase 9 แปลงเป็นน้ำมัน, CO₂ และเงินได้เท่าไร และตัวเลขทุกตัวย้อนกลับไปหา run และแหล่งอ้างอิงได้ไหม

## สรุปสั้น (ระบบ AI เทียบกับแผน static เดิม, 1 plant: รถ 15 คัน ~30 order/วัน)

| | ต่อวัน | ต่อปี (300 วัน) | CI95 ต่อวัน | ข้อสรุป |
|---|---:|---:|---|---|
| CO₂ | **−24.0 kg** (−1.1%) | **−7.2 tCO₂** | [19.6, 28.6] | ลดจริง แต่ไม่มาก |
| ต้นทุนที่วัดได้ (น้ำมัน + ค่าคนขับตอนรอ + ค่าแรงทีมไซต์ตอนว่าง) | **−1,030 THB** (−2.6%) | **−309,000 THB** | [738, 1,327] | ลดจริง |
| ชั่วโมงรถรอที่ไซต์ | −2.5 ชม. (−35%) | −745 ชม. | [1.9, 3.2] | ลดชัดที่สุด |
| เที่ยวที่ส่งไม่ได้ | +0.17 เที่ยว | | แย่กว่า | มาจาก S6 เท่านั้น (ไม่นับ S6: ไม่ต่าง) |

**Story ที่ควรใช้บนสไลด์:** คุณค่าหลักอยู่ที่ **เวลา** (รถรอลดลง 1/3, ทีมไซต์ว่างน้อยลง) ส่วน CO₂ ลดได้ ~1% ต่อ plant ซึ่งตรงกับที่ Phase 6 คาดไว้ว่าน้ำมันตอนจอดรอเป็นส่วนน้อยของน้ำมันทั้งหมด **อย่าขายเป็น "green AI" เป็นหลัก**

## Chain: decision → operational → impact

```text
AI ทำนายเวลาไซต์พร้อม + safety buffer (Phase 9)
   → รถถึงไซต์ใกล้เวลาพร้อมมากขึ้น            รถรอ 431 → 282 นาที/วัน
   → เครื่องยนต์เดินเบาน้อยลง                  idle fuel 21.0 → 13.8 L/วัน   (80% ของน้ำมันที่ลดได้)
   → น้ำมันรวมลดลง 9.0 L/วัน                   × 2.676 kgCO₂/L = 24.0 kgCO₂/วัน
   → เงิน: น้ำมัน 351 + ค่าคนขับตอนรอ 427 + ทีมไซต์ว่าง 251 = 1,030 THB/วัน
```

G3 ตรวจแล้วว่า Δน้ำมัน = Δmoving + Δidle และ ΔCO₂ = Δน้ำมัน × factor ทุกคู่ที่เทียบ

## ผลแยกตาม policy (ค่าเฉลี่ยต่อวัน, 90 วัน-scenario)

| Policy | น้ำมัน (L) | idle (L) | CO₂ (kg) | CO₂/m³ | ต้นทุนที่วัดได้ (THB) | ส่งไม่ได้ |
|---|---:|---:|---:|---:|---:|---:|
| A_static_planned | 799.2 | 21.0 | 2138.5 | 6.60 | 39,317 | 0.47 |
| B_dynamic | 787.6 | 12.5 | 2107.6 | 6.53 | 39,877 | 0.78 |
| C_ai_rolling | **780.0** | **5.2** | **2087.4** | **6.47** | 39,218 | 0.78 |
| B_dynamic_buffered | 792.1 | 16.4 | 2119.8 | 6.57 | 39,206 | 0.71 |
| **C_ai_rolling_buffered** | 790.2 | 13.8 | 2114.5 | 6.54 | **38,287** | 0.63 |

C ที่ไม่มี buffer ประหยัดน้ำมันที่สุด (รถแทบไม่รอเลย) แต่ไซต์ว่างมากจนต้นทุนรวมไม่ลด → เป็นเหตุผลว่าทำไมต้องใช้ตัว buffered ที่ผ่าน gate ใน Phase 9

## เปรียบเทียบแบบ paired (bootstrap ตามวัน, 2000 ครั้ง)

| เทียบ | ขอบเขต | CO₂ ลด/วัน | ต้นทุนลด/วัน | ข้อสรุป |
|---|---|---:|---:|---|
| C_buf เทียบ A | ทุก scenario | 24.0 kg [19.6, 28.6] | 1,030 THB [738, 1,327] | ลดทั้งคู่ |
| C_buf เทียบ A | ไม่นับ S6 | 20.9 kg [16.4, 26.1] | 1,131 THB [890, 1,376] | ลดทั้งคู่ · ส่งไม่ได้ไม่ต่าง |
| C_buf เทียบ B_buf (ผลของ AI) | ทุก scenario | 5.2 kg [−0.9, 11.6] | 919 THB [463, 1,524] | CO₂ **ไม่ต่างชัด** · ต้นทุนลด |
| C_buf เทียบ B_buf | ไม่นับ S6 | 7.0 kg [−0.8, 14.6] | 863 THB [391, 1,470] | CO₂ ไม่ต่างชัด · ต้นทุนลด |

กฎที่ล็อกไว้ก่อนรัน: จะเรียกว่า "ลด" ได้เฉพาะเมื่อ CI95 ไม่คร่อม 0 · ครบทุกแถวอยู่ใน [comparisons.csv](comparisons.csv)

**ข้อควรระวังเรื่อง S6:** ถ้านับทุก scenario น้ำมันที่ลดได้ส่วนหนึ่ง (~1.8 L/วัน) มาจากการที่ C ส่งของใน S6 ได้น้อยกว่า A จึงรายงานแบบไม่นับ S6 และแบบต่อ m³ ควบคู่ไว้เสมอ ซึ่งยังลดได้ทั้งสองแบบ

## Sensitivity (ค่าต่ำ/สูงใน [impact.yaml](../readymix/config/impact.yaml))

| C_buf เทียบ A, ทุก scenario | ต่ำ | กลาง | สูง |
|---|---:|---:|---:|
| CO₂ ลด (kg/วัน) | 22.3 | 24.0 | 24.4 |
| ต้นทุนลด (THB/วัน) | 672 | 1,030 | 1,051 |
| ต่อปี (THB) | 201,000 | 309,000 | 315,000 |

ทิศทางไม่เปลี่ยนในทุก case ค่าต่ำใช้ค่าแรงขั้นต่ำแทนค่าจ้างคนขับรถโม่ ส่วน CO₂ กรณีต่ำนับเฉพาะส่วนฟอสซิลของดีเซล B7

## แหล่งที่มาของค่าที่ใช้ ([impact.yaml](../readymix/config/impact.yaml))

| ค่า | ใช้ | ประเภท | แหล่ง |
|---|---:|---|---|
| CO₂ ดีเซล | 2.676 kg/L (2.489–2.721) | DERIVED | [IPCC 2006 Vol.2 Ch.1](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/V2_1_Ch1_Introduction.pdf): 74,100 kg/TJ × 43.0 TJ/Gg × ความหนาแน่น 0.84 kg/L (ASSUMED) |
| ราคาดีเซล | 39.14 THB/L (33–41.5) | PUBLIC_SOURCE | [GlobalPetrolPrices 07-Sep-2026](https://www.globalpetrolprices.com/Thailand/diesel_prices/), ช่วงราคาจาก [Nation Thailand](https://www.nationthailand.com/news/general/40067011) |
| ค่าจ้างคนขับรถโม่ | 172 THB/ชม. (ต่ำ 50) | PUBLIC_SOURCE | [SalaryExpert, Bangkok](https://www.salaryexpert.com/salary/job/truck-driver-concrete-mixing/thailand/bangkok) |
| ค่าแรงทีมไซต์ | 50 THB/คน-ชม. | DERIVED (ขอบล่าง) | [ค่าแรงขั้นต่ำกรุงเทพฯ 400 THB/วัน](https://pkfthailand.asia/bangkok-raises-minimum-wage-to-400-baht-what-employers-and-workers-should-know/) ÷ 8 ชม. |
| อัตราสิ้นเปลืองรถโม่ (ตรวจช่วง) | 3.03 km/L อยู่ในช่วง 2.5–3.5 | PUBLIC_SOURCE | [HOWO 6 m³ ~33 L/100 km](https://www.howodumptruck.com/fuel-consumption-of-howo-concrete-mixer-trucks/) |
| น้ำมันตอนจอด (ตรวจช่วง) | 3.03 L/ชม. อยู่ในช่วง 2.5–3.5 | PUBLIC_SOURCE | [Argonne: ~0.8 gal/h](https://www.anl.gov/esia/idle-reduction-research) |
| วันทำงานต่อปี | 300 | ASSUMED | 6 วัน/สัปดาห์ |

⚠ Network ของ environment นี้บล็อกการเปิดหน้าเว็บตรง ค่าข้างบนอ่านจากผลค้นหา (search excerpt) และ IPCC ช่วงบน 74,800 kg/TJ มาจากความรู้เดิมเรื่อง Table 1.4 **ต้องเปิดยืนยันทุกลิงก์ก่อนขึ้นสไลด์** ส่วน SalaryExpert และหน้า HOWO เป็นแหล่งเชิงพาณิชย์ ความน่าเชื่อถือต่ำกว่า IPCC/Argonne

## Gate

| Gate | ผล |
|---|---|
| G1 ทุกค่ามี source_type และ source/derivation · บันทึก hash ของ input | PASS ([evaluation_lock.json](evaluation_lock.json)) |
| G2 คำนวณน้ำมัน/ระยะทาง/ไซต์ว่างใหม่จาก log ดิบ ไม่ผ่าน `kpi.py` แล้วตรงกับ Phase 9 | PASS 450/450 run |
| G3 chain ปิดได้ (Δน้ำมัน = Δmoving + Δidle, ΔCO₂ = Δน้ำมัน × factor) | PASS |
| G4 ค่าอ้างอิงสาธารณะอยู่ในช่วง km/L และ idle L/h ที่ simulator ใช้ | PASS |

Tests: `python -m pytest readymix/tests` → **107 passed** (เพิ่ม 3 ข้อใน `test_loop08_impact.py` คำนวณด้วยมือ)

## ข้อจำกัด

- ต้นทุนที่วัดได้**ไม่ใช่กำไร**: ไม่รวมค่าเช่าปั๊ม, ค่าเสียโอกาสของรถ, ความเสี่ยง cold joint และค่าปรับเมื่อส่งไม่ได้ (ไม่มีแหล่งอ้างอิง) · ค่าแรงทีมไซต์ใช้ขอบล่าง
- ต่อปีคือค่าต่อวัน × 300 ของ plant ขนาดจำลอง 1 แห่ง และให้ 9 scenario มีน้ำหนักเท่ากัน ความถี่จริงของแต่ละ scenario ยังไม่รู้
- ไม่รวม CO₂ จากการผลิตคอนกรีต ซึ่งมากกว่าการขนส่งหลายเท่า · ระบบนี้ลดได้เฉพาะส่วนขนส่ง
- ระยะทางเท่ากันทุก policy (V1: 1 เที่ยว 1 ไซต์) CO₂ ที่ลดได้จึงมาจากเวลาจอดรอเกือบทั้งหมด
- ข้อมูลการทำงานเป็น SIMULATED · ตัวคูณทางเศรษฐกิจเป็นค่าจริงหรือค่าที่ derived ตามตารางข้างบน

## ไฟล์และคำสั่ง

```bash
python -m pytest readymix/tests -q --disable-warnings
python phase10_carbon_business/run_loop08.py
```

ผลลัพธ์ (ชุดข้อมูลสำหรับสไลด์ตาม PLAN.md): [carbon_results.csv](carbon_results.csv) · [business_simulation.csv](business_simulation.csv) · [comparisons.csv](comparisons.csv) · [sensitivity.csv](sensitivity.csv) · [impact_runs.csv](impact_runs.csv) · [run.log](run.log)

## ส่งต่อ Phase 11

Dashboard ควรโชว์ BEFORE (A) → AFTER (C_buffered) ด้วยตัวเลขจากไฟล์ในโฟลเดอร์นี้เท่านั้น เน้นชั่วโมงรถรอ ไซต์ว่าง และ THB/วัน ส่วน CO₂ แสดงเป็นตัวรอง พร้อมป้าย SIMULATED
