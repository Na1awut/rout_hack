# Phase 7 — แปลง CVRP เป็นข้อจำกัดของ PrecastFlow ✅

วันที่ 2026-09-28 · สถานะ **PASS** · PrecastFlow contract **1.0**

กำหนด input/output และ constraint layer ที่ตรวจด้วยโค้ดได้แล้ว ตาม [scope ที่อนุมัติใน Phase 6](../phase6_topic_selection/decision.json) มี schema, preparation, independent plan validator และตัวอย่างที่แปลงจากผล Phase 6 จริง โดย CORE-CVRP v1.1 ยังมี freeze_id `bf63a542f2de`

รายละเอียดฉบับใช้งาน: [CONTRACT.md](CONTRACT.md) · [ผลตรวจ](results/verification.json) · [บันทึกทดสอบ](results/tests.txt)

## สิ่งที่ Phase 7 ทำให้ชัดขึ้น

- **ข้อมูลชิ้นงานเป็นแหล่งหลัก:** น้ำหนักและ release อยู่ที่ component; demand/release ของ batch คำนวณจากชิ้นงาน ป้องกันข้อมูลสองชุดไม่ตรงกัน
- **batch เป็น customer node:** หลาย batch อ้าง site/location เดียวกันได้ แต่ยังแยกคิวและลำดับติดตั้ง
- **งานที่เลื่อนมองเห็นเสมอ:** ถ้า batch ไม่พร้อม เลื่อน successors ของไซต์นั้นด้วย และส่ง counts/reasons/ต้นเหตุไปกับผล
- **เวลาจบ service ต้องอยู่ในคิว:** แปลง latest start เป็น slot_end − service_duration และตรวจ release ของทุกชิ้นบนรถก่อนออก
- **ตรวจทั้ง fleet:** ลำดับติดตั้งและ crane overlap ตรวจข้ามรถ ไม่ใช่แค่ทีละ route
- **แยกสถานะตามหลักฐาน:** READY, NO_ELIGIBLE_WORK, INVALID_INPUT, UNSUPPORTED_INPUT และ PROVEN_INFEASIBLE ในขั้นเตรียมข้อมูล; engine หาไม่เจอใช้ NO_FEASIBLE_SOLUTION_FOUND
- **ผูกผลกับ input revision:** case ID + SHA-256 ป้องกันการนำแผนเก่ามารายงานกับข้อมูลที่แก้แล้ว
- **รองรับข้อมูลทางเดินทางอย่างชัดเจน:** explicit distance/time matrices รวม asymmetric travel และ FIFO speed bands แบบจำลองที่กำหนดขอบเขตไว้

## Acceptance

| เกณฑ์ | ผล/หลักฐาน |
|---|---|
| Input/output มีนิยามและหน่วยชัดเจน | ✅ [case schema](schemas/case.schema.json), [plan schema](schemas/plan.schema.json), CONTRACT.md |
| ตรวจความสัมพันธ์ข้อมูลก่อนเข้า solver | ✅ ID, references, component coverage, ordering, provenance labels, travel matrices |
| Constraint layer ส่งข้อมูลพร้อมใช้ | ✅ derived demand/release/latest-start, readiness partition, counts และ proof witnesses |
| ตรวจแผนแยกจาก optimizer | ✅ `validate_contract.py` ไม่ import/call solver ตรวจ C01–C13 ตาม CONTRACT.md |
| ทดสอบข้อผิดพลาดที่เปลี่ยนความหมายคำตอบ | ✅ **47 test methods ผ่าน**, รวม subcases และกรณีคำนวณมือ |
| ใช้กับหลักฐาน Phase 6 ได้ | ✅ **4 input/output pairs ผ่าน** รวม normal/static/readiness/no-work |
| Frozen core ไม่เปลี่ยน | ✅ before = after = Phase 6 reference: `bf63a542f2de` |

### ผลตรวจตัวอย่าง

| Case | Preparation | งานส่ง / งานเลื่อน (ชิ้น) | ผ่านข้อจำกัดของ eligible work | ส่งครบทุกงานที่ร้องขอ |
|---|---|---:|---|---|
| normal — departure choice + FIFO traffic | READY | 36 / 0 | ✅ | ✅ |
| static — static upper-duration model | READY | 36 / 0 | ✅ | ✅ |
| readiness — S2 batch 2 ไม่พร้อม | READY | 30 / 6 | ✅ | ไม่ครบ มี deferred work |
| no_work — ทุกชิ้นไม่พร้อม | NO_ELIGIBLE_WORK | 0 / 36 | ✅ แผนว่างตามสถานะ | ไม่ครบ มี deferred work |

normal/static/readiness เป็นการแปลงและตรวจ **ผลที่บันทึกจาก Phase 6** ไม่ได้รัน optimizer ใหม่ no_work เป็น edge case เพิ่มเพื่อทดสอบ contract ส่วน provenance และ hashes ของต้นทางอยู่ใน [examples/provenance.json](examples/provenance.json)

ตัวตรวจ normal คำนวณได้ตรงผลเดิม: 183,814 m, เดินทางรวม 291 นาทีรถ, รอรวม 803 นาทีรถ, 6 คัน ตัวอย่าง static ใช้ travel model คนละแบบ จึงใช้ยืนยัน interface ไม่ใช้เป็นตาราง savings เทียบกับ normal

### ตัวอย่างที่พิสูจน์ด้วยมือ

ใน `test_contract.py` มี 1 site, 2 batches × 1,000 kg และรถ capacity 3,000 kg ระยะ depot→site 10,000 m / 30 นาที:

```text
ออก 08:30 → ถึง 09:00 → service 09:00–09:20
รอ 40 นาที → service 10:00–10:20 → กลับ depot 10:50
distance = 20,000 m; travel = 60 min; waiting = 40 min
```

ใช้ oracle นี้ตรวจเวลา ระยะและ waiting โดยไม่พึ่ง optimizer อีกชุดหนึ่งจงใจให้รถสองคันใช้เครนซ้อนกัน แล้วตรวจว่าพบทั้ง CRANE_OVERLAP และ INSTALLATION_SEQUENCE

## ขอบเขตความสำเร็จ

Phase 7 ผ่านในฐานะ **ข้อกำหนดข้อมูลและระบบตรวจข้อจำกัด** ไม่ได้เพิ่ม engine ใหม่หรือรับรอง physical loading/crane safety บนหน้างาน `load_plan_approved` ยังเป็น input/assumption ตาม scope และยังไม่มีข้อมูลคาร์บอน/ต้นทุนสำหรับรายงาน impact

READY เป็น necessary-check pass เท่านั้น ไม่รับประกันว่า solver จะหาแผนได้ เช่น 3 batch × 2,000 kg กับรถ 2 × 3,000 kg ผ่าน total-capacity check แต่จัดลงไม่ได้ ตัวทดสอบเก็บกรณีนี้ไว้เพื่อป้องกันการเปลี่ยน READY ให้มีความหมายเกินหลักฐาน

Preparation ปฏิเสธคิวซ้อนและ crane ที่แชร์ข้ามไซต์เป็น UNSUPPORTED_INPUT ภายใต้โมเดล fixed slots นี้ ไม่ตัดสินว่า scheduling รูปแบบอื่นแก้ไม่ได้

## โครงสร้างและวิธีรัน

```text
phase7_constraints/
  PHASE7.md                  ผลและขอบเขตเฟสนี้
  CONTRACT.md                นิยาม input/output/constraints/statuses
  contract.py                schema + preparation + travel evaluation
  validate_contract.py       independent plan validator + CLI
  build_examples.py          แปลงหลักฐาน Phase 6 และ export schemas
  test_contract.py           47 tests (standard-library unittest)
  verify_phase7.py            acceptance + รายงานผลและ hashes
  schemas/                   case.schema.json / plan.schema.json
  examples/                  input/output/prepared 4 ชุด + provenance
  results/                   verification.json / tests.txt
```

```powershell
python phase7_constraints/verify_phase7.py
python phase7_constraints/validate_contract.py phase7_constraints/examples/normal.input.json --plan phase7_constraints/examples/normal.output.json
```

ตัวตรวจข้อมูล/แผนใช้ standard library; acceptance ตรวจ freeze_id ของ Phase 5 ใน environment เดิมด้วย ไม่มี dependency ใหม่

## ส่งต่อ Phase 8 — เตรียม Dataset

1. ใช้ contract 1.0 สร้าง operational dataset ของ PrecastFlow พร้อม source/assumption ทุกกลุ่มข้อมูล แยก published product specs ออกจาก simulated orders/slots/vehicles
2. เก็บข้อมูลระดับ component แล้วแบ่ง approved batches ที่รักษา installation rank; ทุก ID ต้องสัมพันธ์กันและน้ำหนัก batch ให้ระบบคำนวณ
3. ใช้ 36 ชิ้น/12 batches/4 ไซต์จาก Phase 6 เป็นจุดตั้งต้นที่ขนาดอนุมัติแล้ว สร้าง variations ที่มีเหตุผล เช่น production delay, site delay และ fleet shortage พร้อม manifest ระบุสิ่งที่เปลี่ยน
4. เลือก static travel matrices หรือ FIFO simulation อย่างชัดเจน ถ้ามี road matrices จริงให้ระบุที่มา/หน่วย/วิธีได้มาและไม่เรียก Euclidean ว่าระยะถนน
5. แยก calibration/tuning cases ออกจาก evaluation cases ก่อนการเปรียบเทียบใน Phase 10 ทุกวิธีต้องใช้ eligible workload เดียวกัน
6. ตรวจทุก case ด้วย preparation ก่อนส่งต่อ Phase 9; เก็บกรณี unsupported/proven infeasible เป็น negative cases ที่มี expected status โดยไม่ทิ้งออกจากรายงานเงียบ ๆ

Phase 8 เตรียมข้อมูล ส่วน Phase 9 จึงเชื่อม production adapter ให้สร้าง output contract นี้และผ่าน independent validator โดยรักษาขอบเขตที่อนุมัติ
