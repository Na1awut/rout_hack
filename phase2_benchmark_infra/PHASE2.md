# Phase 2 — Benchmark Infrastructure ✅

freeze_id `80b726c457a8` (เหมือนกับ Phase 1 เป๊ะ — พิสูจน์ว่า Phase 2 เรียกใช้ solver ตัวเดียวกัน ไม่ได้แยกไปแก้เอง) · สถานะ **PASS** (2026-09-28)

## สรุปสั้น

เปลี่ยนจาก "ใส่โจทย์ทีละไฟล์แล้วดูผลเอง" เป็น "วางไฟล์ .vrp ในโฟลเดอร์ แล้วรันคำสั่งเดียวได้ CSV ของทุกโจทย์" โดย**ไม่แตะ solver ของ Phase 1 เลย** — batch_runner.py import `cvrp_solver.py`, `validator.py`, และ `freeze.py` จาก `phase1_freeze/` ตรงๆ

```bash
cd 05_core_development/phase2_benchmark_infra
python batch_runner.py benchmarks/
```

| Instance | nodes | cost | BKS | gap | feasible | รันซ้ำได้ผลเดิม | เวลา |
|---|---:|---:|---:|---:|---|---|---:|
| A-n32-k5 | 31 | 784 | 784 | 0.00% | ✅ | ✅ | 8.6 s |
| B-n31-k5 | 30 | 672 | 672 | 0.00% | ✅ | ✅ | 9.4 s |
| P-n19-k2 | 18 | 212 | 212 | 0.00% | ✅ | ✅ | 4.9 s |
| P-n40-k5 | 39 | 458 | 458 | 0.00% | ✅ | ✅ | 16.5 s |

ผลทั้งหมด: [results/phase2_results.csv](results/phase2_results.csv)

---

## Acceptance Criteria (7 ข้อ)

| # | เกณฑ์ | ผ่าน | ทำอย่างไร |
|---|---|---|---|
| 1 | `.vrp` อ่านได้หลาย instance | ✅ | `instance_loader.discover_vrp_files()` สแกนโฟลเดอร์ ใช้ `vrp_parser.py` ของ Phase 1 ตัวเดียว ไม่เขียนใหม่ |
| 2 | `.sol` อ่าน BKS/reference ได้ | ✅ | `sol_parser.py` ใหม่ — ดูรายละเอียดข้อจำกัดด้านล่าง |
| 3 | Batch run ได้โดยไม่แก้ code ทีละโจทย์ | ✅ | เพิ่ม `.vrp` ในโฟลเดอร์ + เพิ่ม entry ใน `fleet_manifest.json` เท่านั้น ทดสอบแล้วว่าไฟล์ที่ไม่มี entry จะถูก **SKIP** พร้อมข้อความเตือน ไม่ใช่เดาจำนวนรถเอง |
| 4 | Validator ตรวจ feasibility แยกจาก solver | ✅ | เรียก `validator.py` ของ Phase 1 ตรงๆ (independent ตั้งแต่ Phase 1 แล้ว) |
| 5 | Distance คำนวณซ้ำ independently | ✅ | อยู่ใน `validator.py` ของ Phase 1 (`recalculated distance matches reported`) |
| 6 | Export CSV อัตโนมัติ | ✅ | `result_schema.py` — schema ล็อกไว้ 21 คอลัมน์ |
| 7 | Environment freeze ที่ OR-Tools `9.15.6755` | ✅ | `requirements.txt` pin ตรงเวอร์ชัน + `freeze.load_config()` เช็คเวอร์ชันจริงตอนรัน ถ้าไม่ตรงจะ error ทันที |

---

## ของใหม่ที่สร้างใน Phase 2

### 1. `sol_parser.py` — อ่านไฟล์ `.sol` แบบ CVRPLIB

รูปแบบ (`Route #1: 21 31 19 ...` แล้วปิดด้วย `Cost 458`) อ้างอิงจาก reference reader ของ [PyVRP/VRPLIB](https://github.com/PyVRP/VRPLIB) รองรับทั้ง `Cost` และ `Cost:` และเก็บบรรทัดอื่นที่ไม่รู้จักไว้ใน `extra_fields` ไม่ทิ้งเงียบ

**ข้อจำกัดที่ต้องบอกตรงๆ:** ไฟล์ `.vrp` ทั้ง 4 ไฟล์ที่มีอยู่ในโปรเจกต์**ไม่มีไฟล์ `.sol` แนบมาด้วย** มีแต่ค่า Optimal ใน COMMENT ของ `.vrp` เอง ดังนั้น parser ตัวนี้ยังไม่ได้ทดสอบกับไฟล์ `.sol` จริงจาก CVRPLIB เลย — ทดสอบด้วยวิธี **round-trip**: เอา route ของ solver เราเขียนเป็น format นี้ (`format_sol_text`) แล้วอ่านกลับมา เทียบว่าตรงกันทุกตัว (ผ่าน) หากทีมได้ไฟล์ `.sol` จริงจาก CVRPLIB มาในอนาคต ต้องเอามาทดสอบ parser ตัวนี้ซ้ำก่อนเชื่อผลเปรียบเทียบ route (ไม่ใช่แค่ cost)

### 2. `instance_loader.py` — จุดเดียวที่โหลดโจทย์

ลำดับความน่าเชื่อถือของค่า reference cost: **`.sol` ไฟล์ > COMMENT ในไฟล์ `.vrp` > ไม่มีเลย** ตอนนี้ทั้ง 4 instance ใช้แหล่งที่ 2 (`reference_source = "comment"` ในผลลัพธ์) เพราะยังไม่มี `.sol` แนบมา

### 3. `fleet_manifest.json` — จำนวนรถเป็นข้อมูล ไม่ใช่โค้ด

ทดสอบแล้วว่าไฟล์ที่ไม่มี entry ในนี้จะถูก skip พร้อม log แทนที่จะเดาจากชื่อไฟล์หรือ DIMENSION — คงกฎเดิมจาก Phase 1 ที่ห้ามเดาจำนวนรถ แม้ตอนนี้จะรันเป็น batch แล้วก็ตาม

### 4. `result_schema.py` — CSV schema ที่ล็อกไว้ล่วงหน้า

21 คอลัมน์ (ดูใน [results/phase2_results.csv](results/phase2_results.csv)) ตั้งใจล็อกตั้งแต่ตอนนี้เพราะ Slide data pack (Phase 16 ของแผน) จะอ่านจากไฟล์นี้ตรงๆ ในอนาคต — เปลี่ยนชื่อคอลัมน์ทีหลังจะพังทุกกราฟที่ต่อจากมัน

### 5. `batch_runner.py` — ตัวเดียวรันทุกโจทย์

- ไม่มี timeout ตายตัวแบบเดา แต่แบ่ง tier ตามขนาดโจทย์ (tiny <50, small <100, medium <250, large <500, stress <1000 — ตรงกับตาราง Phase 4 ในแผน) แต่ **ใช้แค่เป็นเพดานกันค้าง** เกณฑ์หยุดจริงยังเป็น `solution_limit` เดิมจาก Phase 1 ถ้ารอบไหนชนเพดานก่อนครบ solution_limit จะติด `stop_reason=time_cap` ใน notes ทันที และห้ามเอาไปเทียบกับผลที่ freeze แล้ว
- `--no-verify` ปิดการรันซ้ำเพื่อเช็ค determinism (ทดสอบแล้ว: ปิดใช้เวลา ~4.0 s, เปิดใช้เวลา ~10.5 s สำหรับ P-n19-k2 — ตามที่คาดคือเกือบ 2 เท่า) ตอนนี้ปล่อยเปิดไว้เป็น default เพราะมีแค่ 4 instance เมื่อ Phase 4 ขยายเป็นหลายสิบ instance ค่อยพิจารณาปิด default

---

## สิ่งที่ยังไม่ทำใน Phase 2 (ตั้งใจ)

- ไม่แตะเรื่อง `solution_limit = 2000` พอหรือไม่ — เก็บเป็นค่าคงที่ที่ควบคุมไว้ ยกไปตอบใน Phase 4 ตามที่ตกลงกัน
- ไม่มี Docker — ยังไม่จำเป็นสำหรับ hackathon ตราบใดที่ `requirements.txt` พอ
- ยังไม่ได้ทดสอบกับไฟล์ `.sol` จริง (ดูข้อจำกัดข้อ 1 ด้านบน)

## โครงสร้างไฟล์

```text
phase2_benchmark_infra/
├── PHASE2.md
├── requirements.txt          # ortools==9.15.6755 pinned
├── sol_parser.py             # อ่าน .sol แบบ CVRPLIB (ใหม่)
├── instance_loader.py        # จุดเดียวที่โหลดโจทย์ + reference cost (ใหม่)
├── fleet_manifest.json       # max_vehicles ต่อโจทย์ เป็นข้อมูลนอกโค้ด (ใหม่)
├── result_schema.py          # CSV schema ที่ล็อกไว้ (ใหม่)
├── batch_runner.py           # ตัวรันหลัก (ใหม่) — import solver จาก phase1_freeze
├── benchmarks/                # สำเนา .vrp เดียวกับ Phase 1
└── results/phase2_results.csv
```

solver จริงยังอยู่ที่ `phase1_freeze/core/` เท่านั้น Phase 2 ไม่มีสำเนาโค้ด solver ของตัวเอง

## ส่งต่อให้ Phase 3 (Sanity Test)

- ต้องมี instance เล็กมาก (5/10/20/30 customers) ที่คำนวณ distance ด้วยมือได้ เพื่อตรวจ correctness แยกจากการเทียบ BKS
- `batch_runner.py` รับโฟลเดอร์ไหนก็ได้อยู่แล้ว — สร้างโฟลเดอร์ `sanity_instances/` แล้วรันผ่านตัวเดียวกันได้เลย ไม่ต้องเขียน runner ใหม่
