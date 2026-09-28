# Phase 6 — เลือกและยืนยันหัวข้อ

วันที่ 2026-09-28 · สถานะ **PASS — ผู้ใช้ยืนยันหัวข้อและขอบเขตแล้ว**

**ผลตัดสิน: GO สำหรับ PrecastFlow รุ่นที่รับลำดับติดตั้งและคิวเครนที่อนุมัติไว้แล้ว** — จัดรถและเส้นทางให้ทำตามคิวนั้น พร้อมเลือกเวลาออกเดินทาง ใช้เป็น synthetic hackathon prototype ผู้ใช้ยืนยันว่า “ok scale กำลังดีเลย” หลังตรวจข้อเสนอ จึงปิด Phase 6 เป็น PASS และใช้ขอบเขตนี้เป็นฐาน Phase 7 บันทึกการยืนยันอยู่ใน [decision.json](decision.json)

อ่านรายละเอียด: [Problem Definition v1](PROBLEM_DEFINITION_V1.md) · [หลักฐานและข้อจำกัด](EVIDENCE.md) · [คะแนนหัวข้อ](decision_matrix.csv) · [ผลทดลอง JSON](results/gate_summary.json)

## ข้อสรุปจากการเลือกหัวข้อ

ผู้ใช้เป้าหมายคือผู้วางแผนขนส่ง/ผู้ประสานงานติดตั้งพรีแคสต์ ปัญหาที่ทดสอบคือแผนที่ผ่าน capacity และส่งครบอาจยังผิดลำดับติดตั้งหรือผิดคิวเครน เรามีหลักฐานว่าปัญหาประเภทนี้มีอยู่ในงานวิจัย และยืนยันผลิตภัณฑ์ CPAC Extra Precast ได้จากผู้ผลิต แต่ยังไม่ได้สัมภาษณ์ CPAC หรือรับข้อมูลปฏิบัติการจริง

ใช้คะแนน 1–5 ตาม 6 ด้านใน PLAN.md น้ำหนักเท่ากัน คะแนนเป็นวิจารณญาณเพื่อเลือก scope ไม่ใช่ผลทางสถิติหรือคะแนนกรรมการ โดย 1 = fit/หลักฐาน/ความพร้อมต่ำ, 3 = มีเหตุผลรองรับแต่ต้องทดสอบเพิ่มเติม, 5 = เหมาะชัดเจนและมีหลักฐานพร้อมสำหรับโจทย์นี้ Carbon/Business เป็นศักยภาพที่ต้องวัดต่อ ไม่ใช่ savings ที่พิสูจน์แล้ว

| Candidate | Algorithm | Carbon | Business | Novelty | Feasibility | Presentation | รวม /30 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **PrecastFlow — fixed approved sequence/slots** | **4** | **3** | **4** | **3** | **4** | **5** | **23** |
| Ready-mix delivery + time windows | 4 | 3 | 4 | 2 | 4 | 4 | 21 |
| ZERO-MILE backhaul | 4 | 3 | 4 | 2 | 3 | 5 | 21 |
| Construction waste routing | 4 | 3 | 3 | 2 | 4 | 4 | 20 |
| Precast full joint route/crane/sequence/traffic | 3 | 3 | 4 | 3 | 2 | 5 | 20 |
| Ready-mix + pump | 2 | 3 | 4 | 3 | 2 | 4 | 18 |
| Ultra bridge girder | 2 | 3 | 4 | 3 | 2 | 4 | 18 |
| Extra base layer | 3 | 2 | 3 | 3 | 3 | 3 | 17 |

เหตุผลของคะแนน PrecastFlow:

- **Algorithm 4:** capacity-only projection ใช้ frozen core ได้จริง; extension ยังต้องใช้ batch nodes และ time windows ต่างจาก wrapper เดิม จึงไม่ให้ 5
- **Carbon 3:** มีช่องทางวัด travel/load/idle แต่ยังไม่มี fuel calibration และไม่รับประกันว่าระยะทางจะลด
- **Business 4:** การส่งตรงคิวและลดการรอเชื่อมกับงานผู้วางแผนได้ชัด มีหลักฐานปัญหาจากงานวิจัย แต่ยังไม่มีข้อมูลมูลค่าจาก CPAC
- **Novelty 3:** JIS/การประสานขนส่งกับหน้างานมีงานเดิมแล้ว จุดต่างของทีมอยู่ที่ case การตรวจผล และการเปรียบเทียบ ไม่อ้างว่าเป็นอัลกอริทึมใหม่หรือไม่มีทีมอื่นทำ
- **Feasibility 4:** probe รันจริงและผ่านการตรวจ แต่ยังสมมติ batch/load plan และ traffic ขนาดเล็ก
- **Presentation 5:** แสดงการส่งครบแต่ผิดคิว เทียบกับแผนที่ผ่านลำดับ/คิวได้ตรงไปตรงมา ไม่ต้องอาศัยตัวเลขคาร์บอนที่ยังไม่มี

Ready-mix แบบจำกัด scope มีข้อมูลผลิตภัณฑ์/บริการจาก CPAC ชัดและใช้ time windows ได้ แต่คำอธิบายต้องต่างจากบริการจอง/ติดตามที่มีอยู่แล้ว ZERO-MILE ต้องยืนยันงานขากลับและ compatibility ส่วน waste, base layer และ bridge ยังไม่มี operational case ที่ตรวจละเอียดเท่า Precast ในรอบนี้ คะแนนหัวข้อเหล่านี้เป็นการคัดกรองเบื้องต้น ไม่ใช่การทดลองเทียบความสามารถจริง ความได้เปรียบ 2 คะแนนของ PrecastFlow ไม่แข็งแรงพอจะใช้แทนเหตุผล: หากลด Feasibility กับ Algorithm อย่างละ 1 จะเสมออันดับรอง

## Decision Gate ตาม idea.md

| Gate | หลักฐาน/ผล | สถานะ |
|---|---|---|
| 1. specification สินค้า 2–3 ชนิด | ใบข้อมูลผู้ผลิตหน้า 2 ระบุผนัง/พื้นและช่วงความหนา ใช้ผนัง 100 mm และพื้น 120 mm; ความยาว/กว้าง/มวลจำลองเปิดเผยในข้อมูล | **ผ่านสำหรับ synthetic prototype**; ยังไม่มีน้ำหนักต่อชิ้นหรือ load plan จริง |
| 2. synthetic orders 30–50 รายการ | สร้าง 36 component IDs, 12 batches, 4 sites, 1 depot | **ผ่าน** |
| 3. map เข้า core ปัจจุบัน | `.vrp` 12 customer nodes รัน frozen v1.1 และ validator เดิมผ่าน | **ผ่าน** |
| 4. time window + sequence โดยไม่รื้อ core | fixed-slot adapter ใช้ PyVRP 0.14.0 ที่ติดตั้งอยู่, independent validation ข้ามรถ/เครน, freeze_id ก่อนหลังตรงกัน | **ผ่านเฉพาะ fixed approved slots/sequence** |

**คำตัดสินทางเทคนิค:** GO สำหรับ scope ข้างต้น; ยังไม่ GO สำหรับระบบที่หาลำดับติดตั้ง/คิวเครน/route/traffic พร้อมกันอย่างอิสระหรือพร้อมใช้งานจริงที่ CPAC

## ผลทดลองจริง

รัน `python phase6_topic_selection/feasibility_probe.py` ได้ **21/21 checks ผ่าน** รายการและรายละเอียดอยู่ใน [gate_checks.csv](results/gate_checks.csv) และ [gate_summary.json](results/gate_summary.json)

Dataset เป็นข้อมูลสมมติทั้งหมดในส่วน operation: 36 ชิ้นรวม 51,156 kg, 12 batch, 6 คัน × 9,000 kg, depot เดียว, 4 ไซต์, 3 คิวต่อไซต์ มีทั้ง route หลายไซต์และหลาย batch ในไซต์เดียวกัน พิกัดเป็นเมตรบนระนาบสมมติและปัดระยะตาม core ไม่ใช่ถนนจริง

| ทดลอง | ผล |
|---|---|
| Pure CVRP projection | feasible ตาม capacity, ระยะทาง 183.814 km; เมื่อนำไปตรวจคิวพบ late 2 batch และ sequence violations 2 คู่ |
| Fixed-slot extension seeds 1/2/3 | ทั้ง 3 แผนผ่าน independent capacity/coverage/release/window/sequence/crane checks, ระยะ 183.814 km และ 6 คันทุก seed |
| รัน seed 1 ซ้ำ | route + departure fingerprint ตรงกันใน environment นี้; ไม่ใช่การทดสอบข้ามเครื่อง |
| ไซต์ S2 ไม่พร้อมตั้งแต่ batch 2 | เลื่อน batch 2 และ successor batch 3 ออก 6 ชิ้น แผนของงานที่เหลือ 30 ชิ้นผ่าน; รายงานงานเลื่อนชัดเจน |
| Production release ของ S1-B3 เลื่อนไป 10:00 | แผนที่ได้ไม่ออกรถพร้อมชิ้นงานนั้นก่อนเวลา release และผ่านตัวตรวจอิสระ |
| Input/validator failures | จับ batch หนักเกิน, fleet capacity ไม่พอ, คิวสั้นเกิน, คิวซ้อนที่ adapter ไม่รองรับ, load plan ไม่อนุมัติ, งานหาย/ซ้ำ, late plan และ crane overlap ข้ามรถได้ |
| Solver หาแผนไม่ได้ | รายงาน `NO_FEASIBLE_SOLUTION_FOUND` ไม่ใช้เป็น proof of infeasibility; กรณีจงใจทำ shift ใช้งานไม่ได้มี PyVRP `PenaltyBoundWarning` ตามคาด |

**สิ่งที่ผลนี้แสดง:** สามารถเพิ่มความถูกต้องด้าน operation โดยไม่ต้องลดความถูกต้อง CVRP หรือแก้ frozen core; ระยะทางและจำนวนรถในตัวอย่างนี้ไม่ได้ลดลง

### Departure-time probe บน route ชุดเดียวกัน

ใช้ traffic สมมติแบบ FIFO คำนวณตามเวลาแต่ละ leg แล้วค้นเวลาออกทุกนาที ภายใต้คิวเดิมทุกวิธี:

| เวลาออก | Travel รวม (นาทีรถ) | Truck waiting รวม (นาทีรถ) | ระยะทาง | รถ |
|---|---:|---:|---:|---:|
| ทุกคัน 07:00 — baseline จำลองแบบง่าย | 401 | 1,675 | 183.814 km | 6 |
| ตาม schedule จาก static solver | 304 | 900 | 183.814 km | 6 |
| เลือกเวลาออกด้วย traffic จำลอง | 291 | 803 | 183.814 km | 6 |

การเปรียบเทียบหลักควรใช้ schedule จาก solver: travel ลด 13 นาทีรถ และ waiting ลด 97 นาทีรถในเคสนี้ ตัวเลขรวมหลายคัน ไม่ใช่ระยะเวลาจบงานทั้งวัน ค่าเทียบ 07:00 แสดงไว้เพื่อความโปร่งใส ไม่ใช้ขยายคำอ้างผลประหยัด ไม่มีการแปลงเวลาที่ลดเป็น CO₂/เงิน เพราะยังไม่มีแบบจำลองและ calibration

ผลขนาดเล็กนี้เป็น feasibility test ไม่ใช่ performance benchmark หรือหลักฐาน business impact ยังต้องทดสอบหลายโครงสร้างข้อมูลและกรณีที่ trade-off แย่ลงใน Phase 10/14

## ข้อแก้ไขสำคัญที่พบระหว่างตรวจ

**Engine จริงคือ PyVRP ILS:** local `Model.solve()` เรียก `IteratedLocalSearch` และเอกสาร PyVRP ยืนยันการเปลี่ยนตั้งแต่ 0.13.0 ชื่อ HGS ใน Phase 5 จึงคลาดเคลื่อน ได้แนบ erratum ในเอกสาร Phase 5 โดยเก็บ frozen code/config เดิม ผล freeze_id ยังเป็น `bf63a542f2de` รายละเอียดใน [EVIDENCE.md](EVIDENCE.md)

**Original v1.1 wrapper ยังไม่มี time-window interface:** ความสามารถที่พิสูจน์รอบนี้มาจาก adapter ใหม่ที่ใช้ engine เดียวกัน ไม่ใช่แค่ส่ง config เพิ่มเข้า `solve_cvrp()` เดิม

## หัวข้อและขอบเขตที่ผู้ใช้ยืนยันแล้ว

> เลือก **PrecastFlow** สำหรับ CPAC Extra Precast เป็นหัวข้อหลัก ใช้ **synthetic operational case** ที่อิงชนิด/ความหนาสินค้าจริง รุ่นแรกมี **1 depot, approved delivery batches, payload capacity, readiness, fixed crane slots, fixed installation sequence และ departure-time choice** โดยรับลำดับ/คิวจากผู้วางแผน ไม่อ้างผลคาร์บอนหรือ business savings จนกว่าจะวัดในเฟสถัดไป

ผู้ใช้ยืนยันขอบเขตนี้แล้ว ขั้นถัดไปคือ Phase 7 โดยใช้ Problem Definition v1 เป็นฐาน การยืนยันครั้งนี้ครอบคลุมหัวข้อและขอบเขต prototype ส่วนสมมติฐาน operational data และข้อจำกัดของผลทดลองยังเป็นไปตามที่ระบุ หากขยายเป็น arbitrary sequence/crane scheduling ต้องทบทวน gate 4 เพราะผลรอบนี้ยังไม่รองรับ scope นั้น

## ไฟล์ส่งมอบและวิธีรัน

- `PHASE6.md`: decision memo นี้
- `decision.json`: บันทึกการอนุมัติหัวข้อ/ขอบเขตจากผู้ใช้ แยกจากผลทดลองที่สร้างใหม่ได้
- `PROBLEM_DEFINITION_V1.md`: node/demand/vehicle/constraint/objective/KPI/assumptions
- `EVIDENCE.md`, `evidence/`: แหล่งต้นฉบับ ภาพหน้า PDF และหลักฐานชื่อ engine
- `decision_matrix.csv`: 6 เกณฑ์ตาม PLAN.md
- `data/components.csv`, `data/delivery_batches.csv`, `data/synthetic_case.json`: dataset เปิดเผยสมมติฐาน
- `data/capacity_projection.vrp`: input ที่ frozen core อ่านได้จริง
- `feasibility_probe.py`, `results/`: สคริปต์และผลดิบ รวม route/schedule ที่ตรวจได้

```powershell
python phase6_topic_selection/feasibility_probe.py
```

ใช้ environment เดิมที่ pin `pyvrp==0.14.0` และ dependency ของ Phase 5 สคริปต์เขียนทับเฉพาะ generated data/results ของ Phase 6 เมื่อรันซ้ำ รหัส hash dataset/probe และ Python/platform บันทึกใน summary; runtime อาจเปลี่ยนได้
