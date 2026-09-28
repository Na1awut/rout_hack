# Phase 12 — Stress Test + Failure Cases (Loop 9) ✅

สถานะ **PASS** (2026-09-28) · gate ผ่าน 5/5 ([gates.json](gates.json)) · ใช้วันใหม่ 9201–9205 ที่ไม่เคยใช้ · [config.json](config.json) commit ก่อนรัน

> **คำถาม:** เมื่องานล้น รถเสีย ข้อมูลเสีย หรือ AI พัง ระบบตอบด้วยสถานะที่ชัดเจน (หรือ "ต้องเพิ่มรถอีก N คัน") แทนที่จะ crash หรือได้แผนที่ผิดกฎหรือไม่

## สรุปสั้น

- **ไม่มี crash ในผลรอบสุดท้าย** · 105 stress run และ 11 fault ได้สถานะที่อธิบายได้ทุกครั้ง · ทุกแผนที่รันผ่าน execution validator
- **Fault injection เจอบั๊กจริง 2 ตัวและแก้แล้ว:** กรณีไม่มีรถเข้ากะเลย `fleet_check` ดึงจาก heap ว่าง และ `kpi.py` หารด้วยศูนย์ · ผลของกรณีปกติไม่เปลี่ยน (Phase 9 และ Phase 10 รันซ้ำได้ตรงเดิม · 117 tests ผ่าน)
- **จุดอ่อนที่ต้องบอกกรรมการ:** เมื่อ **งานเกินกำลังรถ** (demand +50%, รถเหลือ 10 คัน, รถติดสุดขีด) แผน static เดิมยังดีกว่า AI · AI ชนะชัดเมื่อปัญหาอยู่ที่ **ไซต์** (ล่าช้าหลายจุด, ประกาศเวลาพร้อมผิด)

## สิ่งที่สร้าง

| ไฟล์ | หน้าที่ |
|---|---|
| [fleet_check.py](../readymix/application/fleet_check.py) | ก่อนเริ่มวัน: จำลองแผนด้วยข้อมูลที่รู้ล่วงหน้า (ไซต์พร้อมตามนัด, traffic ปกติ) → **INFEASIBLE** "ต้องเพิ่มรถอีก N คัน" / **AT_RISK** "มี X เที่ยวที่คาดว่าช้าเพราะรถไม่พอ" / OK · ไม่มี threshold ให้จูน · แยก "ช้าเพราะแผนลูกค้าหรือ bay" ออกจาก "ช้าเพราะรถ" |
| [safe_dispatch.py](../readymix/application/safe_dispatch.py) | `run_safely()`: ตรวจข้อมูล → fleet check → dispatch (ถ้าโหลดโมเดลไม่ได้ ให้ใช้ dispatch แบบไม่มี AI) → ตรวจแผนที่รันแล้ว · คืนสถานะ REJECTED_DATA / OK / DEGRADED แทนการ raise |
| [stress_scenarios.yaml](stress_scenarios.yaml), [simulation_fleet10.yaml](simulation_fleet10.yaml) | stress scenario แยกไฟล์ · ไม่แก้ config เดิม เพื่อให้ dataset ของ Phase 6–11 ตรงเดิมทุก byte |

## ส่วนที่ 1 — Stress scenarios (5 วัน × 7 แบบ × 3 policy = 105 run)

Score = รถรอ + ไซต์ว่าง + 1000 × เที่ยวที่ส่งไม่ได้ (นาที, ยิ่งต่ำยิ่งดี) · C = AI + buffer (Phase 9), B = dynamic ไม่มี AI + buffer, A = แผน static

| Stress | A | B | **C** | C ต่างจาก A | C ชนะ A (วัน) | C ต่างจาก B | ส่งไม่ได้ A / B / C |
|---|---:|---:|---:|---:|---:|---:|---|
| X1 demand +50% | **5095** | 5725 | 6136 | +24.9% | 1/5 | +9.3% | 2.4 / 2.8 / 3.2 |
| X2 รถเสีย 4 คัน | **1591** | 1775 | 1676 | +5.0% | 2/5 | −5.8% | 0 / 0 / 0 |
| X3 ไซต์วุ่น (ล่าช้า 6, ปั๊มเสีย 3, เทช้า 3) | 2061 | 1228 | **1054** | **−47.3%** | 5/5 | −15.2% | 0 / 0 / 0 |
| X4 ไซต์ประกาศเวลาพร้อมผิด 10 จุด | 1356 | 1032 | **910** | **−32.3%** | 5/5 | −11.0% | 0 / 0 / 0 |
| X5 รถติดสุดขีด + ฝน | **3698** | 4284 | 3907 | +10.5% | 3/5 | −8.5% | 1.4 / 1.6 / 1.4 |
| X6 ทุกอย่างพร้อมกัน | 22037 | 22138 | **21131** | −2.7% | 4/5 | −4.8% | 18.0 / 18.8 / 18.0 |
| X7 รถเหลือ 10 คัน | **7479** | 7937 | 7602 | +16.4% | 1/5 | +1.8% | 4.4 / 4.6 / 4.2 |

ไฟล์: [stress_summary.csv](stress_summary.csv), [stress_metrics.csv](stress_metrics.csv) (เก็บ log_sha256 ทุก run)

**อ่านผล:** C ดีกว่า B ใน 5/7 แบบ ซึ่งยืนยันว่า AI ช่วยเมื่อกลไก dispatch เหมือนกัน แต่ระบบ dynamic (B และ C) **แพ้แผน static เมื่องานเกินกำลังรถ** (X1, X7 และ S6 ใน Phase 9) · สาเหตุที่น่าจะเป็นคือ dispatcher ปล่อยรถทีละเที่ยวต่อ order แบบ just-in-time ส่วนแผน static ปล่อยตามตารางล่วงหน้าจึงใช้รถได้เต็มกว่าเมื่อรถขาด · **ควรทำต่อ:** ให้ fleet check ที่ขึ้น INFEASIBLE สลับไปใช้โหมดล้นกำลัง (ปล่อยล่วงหน้าหรือจัดลำดับ order) · ยังไม่ได้ทำใน Phase นี้

## ส่วนที่ 2 — จงใจทำให้พัง (11 fault บนวัน X3 day 9201)

| Fault | คาดไว้ | ได้ | ระบบตอบว่า |
|---|---|---|---|
| F01 รถเสียทุกคันตอน 09:00 | DEGRADED | ✅ DEGRADED | ส่งไม่ได้ 61 เที่ยว (แผนยัง valid ทุกเที่ยวที่ส่ง) |
| F02 ไซต์ที่ไม่มีข้อมูลเส้นทาง | REJECTED_DATA | ✅ | traffic.csv: edge P001->S001 does not cover every hour slot |
| F03 ไม่มีรายงานสถานะไซต์เลย | OK/DEGRADED | ✅ OK | AI ใช้ planned + ประกาศแทนเอง ส่งครบ |
| F04 AI crash ทุกครั้งที่เรียก | DEGRADED | ✅ | AI error 212 ครั้ง ใช้เวลาตามแผน + ประกาศแทน · **log ตรงกับ dispatch แบบไม่มี AI ทุก byte** (มี test) |
| F05 ไฟล์โมเดลหาย | DEGRADED | ✅ | AI ใช้ไม่ได้ (FileNotFoundError) ใช้ dispatch แบบไม่มี AI แทน |
| F06 เที่ยว 9 m³ แต่รถจุ 6 m³ | REJECTED_DATA | ✅ | volume 9.0 does not fit capacity 6.0 |
| F07 แก้ไฟล์หลังสร้างโดยไม่อัปเดต manifest | REJECTED_DATA | ✅ | sha256 does not match manifest |
| F08 วันที่ไม่มี order | OK/REJECTED | ✅ OK | ไม่มี order วันนี้ |
| F09 ไม่มีรถเข้ากะเลย | DEGRADED | ✅ (หลังแก้บั๊ก) | ก่อนเริ่มวัน: คาดว่าส่งไม่ทัน 77 เที่ยว **ต้องเพิ่มรถอีก 12 คัน** |
| F10 ข้อมูล traffic ช่วง 12:00 หาย | REJECTED_DATA | ✅ | travel_profile.csv does not cover every traffic hour |
| F11 AI ส่งค่าขยะ (NaN, เวลาผิดรูปแบบ) | DEGRADED | ✅ | ตรวจ output contract ไม่ผ่าน · fallback 212 ครั้ง |

ไฟล์: [fault_results.csv](fault_results.csv) · ข้อมูลที่ถูกแก้อยู่ใน `faults/` (สร้างซ้ำได้ด้วยสคริปต์)

## ส่วนที่ 3 — Fleet check บอกความจริงไหม

บน stress days ดูจากผลของแผน static (A):

| | จำนวน |
|---|---:|
| วันที่ขึ้น INFEASIBLE "ต้องเพิ่มรถ" | 5 · **ทั้ง 5 วันส่งไม่ครบจริง** (ไม่มี false alarm) |
| วันที่ A ส่งไม่ครบ | 12 · ขึ้น INFEASIBLE 5 วัน, AT_RISK 7 วัน, OK 0 วัน |
| วันที่ขึ้น AT_RISK | 30 จาก 35 |

ใน Phase 9 (90 วัน-scenario) INFEASIBLE ถูกต้อง 5/5 วันเช่นกัน

**ข้อจำกัด:** INFEASIBLE พลาด 7 วันที่ส่งไม่ครบเพราะเหตุการณ์ระหว่างวัน เช่น รถเสีย, demand เปลี่ยน หรือรถติดหนักกว่าปกติ ซึ่งการเช็กก่อนเริ่มวันไม่มีทางรู้ · AT_RISK ขึ้นเกือบทุกวันเพราะรถ 15 คันไม่พอต่อช่วงพีคจริงในโลกจำลองนี้ (สอดคล้องกับ on-time ประมาณ 0.7) จึงใช้คัดวันไม่ได้ ใช้ได้แค่บอกว่า "ควรเพิ่มรถกี่คัน" · G4 ผ่านเพราะไม่มีวันที่ส่งไม่ครบแต่ขึ้น OK ถือเป็นเกณฑ์ที่หลวม

## Gate

| Gate | ผล |
|---|---|
| G1 ไม่ crash (ไม่มี ERROR หรือ exception หลุด) | PASS · ครั้งแรกไม่ผ่านที่ F09 → แก้บั๊ก 2 ตัว → PASS |
| G2 ทุกแผนที่รันผ่าน execution validator | PASS 105/105 + fault ที่รันได้ทั้งหมด |
| G3 ทุก fault ได้สถานะตามที่คาดไว้พร้อมข้อความ | PASS 11/11 |
| G4 fleet check ไม่บอกว่ารถขาดโดยไม่จริง และไม่บอก OK ในวันที่ส่งไม่ครบ | PASS (ดูข้อจำกัดด้านบน) |
| G5 Core benchmark ยังได้ผลเดิม | PASS · 8/8 run ตรง snapshot ([core_regression.log](core_regression.log)) · freeze_id บน Linux ยังต่างจากที่ล็อก เหมือนที่รายงานไว้ใน Phase 9 |

Tests: `python -m pytest readymix/tests` → **117 passed** (เพิ่ม `test_loop09_stress.py` 5 ข้อ)

## คำสั่ง

```bash
export OMP_NUM_THREADS=1
python phase12_stress_test/run_loop09.py 4
python -m pytest readymix/tests -q --disable-warnings
```

## ส่งต่อ Phase 13

- สไลด์ต้องมีหน้า "เมื่อไรที่ AI ไม่ช่วย": งานล้นกำลังรถ → ระบบบอกให้เพิ่มรถแทน
- ตัวอย่างข้อความ graceful สำหรับเดโม: F09 "ต้องเพิ่มรถอีก 12 คัน" และ F05 "AI ใช้ไม่ได้ ใช้ dispatch แบบไม่มี AI แทน"
