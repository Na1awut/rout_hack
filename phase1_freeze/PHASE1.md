# Phase 1 — Freeze Core Algorithm ✅

**CORE-CVRP v1.0** · freeze_id `80b726c457a8` · สถานะ **PASS** (2026-09-28)

## สรุปสั้น

ล็อก solver ไว้เป็นเวอร์ชันเดียว และเปลี่ยนวิธีหยุดการค้นหาจาก**เวลา**เป็น**ปริมาณงาน** ผลคือรันกี่ครั้งหรือบนเครื่องไหนก็ได้คำตอบเดิมทุกตัว ทั้งระยะทางและชุดเส้นทาง

| Instance | ระยะทาง | Optimal | Gap | รันซ้ำได้ผลเดิม | เวลา (เครื่องว่าง) |
|---|---:|---:|---:|---|---:|
| A-n32-k5 | 784 | 784 | 0.00% | ✅ | 8.5 s |
| B-n31-k5 | 672 | 672 | 0.00% | ✅ | 8.1 s |
| P-n40-k5 | 458 | 458 | 0.00% | ✅ | 13.7 s |
| P-n19-k2 | 212 | 212 | 0.00% | ✅ | 4.1 s |
| P-n40-k5 ตอน CPU โหลดหนัก | 458 | 458 | 0.00% | ✅ เส้นทางตรงกับตอนเครื่องว่าง | 36.5 s |

ตัวเลขทั้งหมดมาจาก [results/phase1_results.csv](results/phase1_results.csv)

---

## ปัญหาที่เจอก่อน freeze

solver เดิม (ใน `04_hackathon_qualifier`) หยุดตามเวลา ทดลองแล้วพบว่า**ผลขึ้นกับความเร็วเครื่อง**

| P-n40-k5 (optimal 458) | เครื่องว่าง | CPU โหลดหนัก |
|---|---|---|
| หยุดที่ 1.5 วินาที | 468, 468, 468, 468, 468 | **478, 478, 494** |
| หยุดเมื่อครบ 2,000 solution | 458 ทุกรอบ | 458 ทุกรอบ |

สไลด์ของงานแข่งบอกว่าผู้จัดจะนำโค้ดไปรันซ้ำ ถ้าเครื่องกรรมการช้ากว่าเครื่องเรา เขาจะได้ตัวเลขที่แย่กว่าที่เรารายงาน ทั้งที่เราไม่ได้แต่งตัวเลขเลย

รันซ้ำได้ด้วย `evidence/time_vs_work_stop.py` และ `evidence/time_vs_work_stop_loaded.py`

---

## สิ่งที่ทำต่างจากวิธีปกติ

วิธีปกติคือจด seed, พารามิเตอร์, time limit และสเปคเครื่องไว้ เราทำเพิ่มดังนี้

| # | สิ่งที่ทำ | เทียบกับวิธีปกติ | อ้างอิง |
|---|---|---|---|
| 1 | **หยุดด้วยปริมาณงาน** (`solution_limit = 2000`) แทนนาฬิกา เวลายังคงไว้แค่เป็นเพดานกันค้าง (600 s) รอบไหนชนเพดานจะถูกติดป้าย `time_cap` และไม่นับเป็นผล freeze | **ดีกว่า** เพราะผลไม่ขึ้นกับเครื่อง | WorkLimit ของ [Gurobi](https://docs.gurobi.com/projects/optimizer/en/current/concepts/parameters/guidelines.html), การปรับเวลาด้วย PassMark ของ [DIMACS VRP Challenge](http://dimacs.rutgers.edu/programs/challenge/vrp/cvrp/) |
| 2 | **ล็อกค่าอ้างอิงไว้ก่อนทดลอง** (`reference_bks.json`, policy = version-frozen) และวัด **anytime score** บนแกนจำนวน solution | **ดีกว่า** เพราะวัดความเร็วในการลู่เข้าได้ ไม่ใช่แค่ Gap สุดท้าย | [Normalized Signed Primal Integral, arXiv 2608.18288](https://arxiv.org/abs/2608.18288) |
| 3 | **ประกาศวิธีปัดระยะทาง**ใน config: `floor(d + 0.5)`, ไม่ scale | **เทียบเท่า** แต่ชัดเจนกว่า | [Scaling & rounding in VRPTW, arXiv 2606.09196](https://arxiv.org/abs/2606.09196) |
| 4 | **freeze_id** = hash ของ config + ค่าอ้างอิง + โค้ด solver + ไฟล์โจทย์ + เวอร์ชัน OR-Tools ติดอยู่ทุกแถวของผลลัพธ์ | **ใหม่** ทุกตัวเลขตรวจย้อนได้ว่ามาจาก build ไหน | แนวทางตรวจซ้ำได้ของ [Accorsi, Lodi & Vigo (2022)](https://arxiv.org/abs/2109.13983) |
| 5 | **ตรวจชุดเส้นทาง ไม่ใช่แค่ต้นทุน** (route fingerprint) เพราะสองชุดเส้นทางอาจมีระยะรวมเท่ากัน | **ดีกว่า** | — |

### anytime score คืออะไร

```text
gap(c) = (c − ref) / max(c, ref)       ช่วงค่า (−1, 1), ก่อนเจอ solution แรก = 1
score  = ค่าเฉลี่ยของ gap ตลอด solution ที่ 1 ถึง 2,000
```

- 0 = ได้คำตอบ optimal ตั้งแต่ solution แรก ยิ่งต่ำยิ่งดี
- ค่าติดลบได้ ถ้าวันหนึ่งหาคำตอบที่ดีกว่าค่าอ้างอิง
- สูตรนี้**เป็นสูตรที่เราเลือกเอง** ตามแนวคิดของงานวิจัยข้างต้น ไม่ใช่สูตรที่คัดลอกมาตรงตัว

| Instance | anytime score |
|---|---:|
| B-n31-k5 | 0.0011 (ลู่เข้าเร็วสุด) |
| A-n32-k5 | 0.0069 |
| P-n40-k5 | 0.0144 |
| P-n19-k2 | 0.0265 (ลู่เข้าช้าสุด แม้โจทย์เล็กสุด) |

P-n19-k2 เล็กที่สุดแต่ลู่เข้าช้าที่สุด แปลว่าความยากไม่ได้ขึ้นกับจำนวนลูกค้าอย่างเดียว เป็นข้อสังเกตที่ควรตามต่อใน Phase 5 ตอนทำ Strength Profile

---

## สิ่งที่แก้ระหว่าง freeze

solver เดิมรายงานสถานะ `OPTIMAL` ทุกครั้งที่ OR-Tools ตอบว่า `ROUTING_SUCCESS` ซึ่ง**ไม่ถูกต้อง** เพราะ `ROUTING_SUCCESS` แปลแค่ว่าหาคำตอบเจอ ส่วน local search ไม่เคยพิสูจน์ optimality ได้เลย เวอร์ชัน freeze จึงรายงานเป็น `FEASIBLE` และแยก `stop_reason` ออกมาต่างหาก

ต้นทุนที่ได้ยังตรงกับ optimal ทุกตัว แค่เลิกเขียนว่าพิสูจน์แล้ว ทั้งที่ยังไม่ได้พิสูจน์

## ข้อแลกเปลี่ยน

- **ช้าลง:** เดิม P-n40-k5 ได้ 458 ภายในไม่กี่วินาทีด้วย time limit ตอนนี้ใช้ 13.7 s บนเครื่องว่าง และ 36.5 s ตอนเครื่องโหลด ยอมแลกเพื่อให้ได้ผลที่รันซ้ำได้
- **ต้องใช้ OR-Tools 9.15.6755 เท่านั้น:** ถ้าเวอร์ชันไม่ตรง `freeze.py` จะไม่ยอมรัน เพราะ engine ต่างเวอร์ชันอาจค้นหาต่างกัน
- **2,000 solution ยังไม่ได้พิสูจน์ว่าพอสำหรับโจทย์ใหญ่:** ต้องตรวจใน Phase 4 ถ้าโจทย์ 500+ จุดใช้ไม่พอ ต้องออกเป็น v1.1 พร้อม freeze_id ใหม่ ห้ามแก้ของ v1.0

---

## โครงสร้างไฟล์

```text
phase1_freeze/
├── PHASE1.md                     # เอกสารนี้
├── algorithm_config.json         # นิยามของ algorithm ทั้งหมด (search, stop rule, distance convention)
├── reference_bks.json            # ค่าอ้างอิงที่ล็อกไว้ก่อนทดลอง + จำนวนรถต่อโจทย์
├── freeze.py                     # freeze_id, route fingerprint, anytime score, ตรวจเวอร์ชัน OR-Tools
├── verify_freeze.py              # acceptance test ของ Phase 1
├── core/                         # solver ที่ freeze แล้ว (คัดลอกจาก 04 แล้วปรับ)
│   ├── vrp_parser.py             #   ไม่แก้
│   ├── distance.py               #   ไม่แก้
│   ├── validator.py              #   ไม่แก้
│   ├── cvrp_solver.py            #   อ่าน config, หยุดด้วย solution_limit, แก้ป้าย OPTIMAL
│   └── anytime_tracker.py        #   เพิ่มแกน solution_index
├── benchmarks/                   # A-n32-k5, B-n31-k5, P-n40-k5, P-n19-k2
├── evidence/                     # สคริปต์ที่พิสูจน์ปัญหาของ time limit
└── results/phase1_results.csv    # ผลลัพธ์ (มี freeze_id ทุกแถว)
```

## วิธีรัน

```bash
cd 05_core_development/phase1_freeze
python verify_freeze.py            # ครบทุกขั้น รวมทดสอบตอน CPU โหลด (~2 นาที)
python verify_freeze.py --no-load  # ข้ามขั้นทดสอบตอน CPU โหลด
```

## กติกาหลัง freeze

- ห้ามแก้ไฟล์ใน `core/` และ `algorithm_config.json` ของ v1.0 ถ้าจำเป็นต้องแก้ให้ออกเวอร์ชันใหม่ ซึ่ง freeze_id จะเปลี่ยนเองอัตโนมัติ
- phase ต่อไปต้อง import solver จาก `phase1_freeze/core/` ไม่คัดลอกไปแก้เอง

## ส่งต่อให้ Phase 2 (Benchmark Engine)

- ขยาย `verify_freeze.py` ให้เป็น benchmark runner ที่รับโจทย์ได้หลายชุด
- ต้องมีตัวอ่านไฟล์ `.sol` (ตอนนี้ยังไม่มี) เพื่อดึง BKS ของโจทย์ที่ COMMENT ไม่ได้ระบุ optimal
- ต้องแยก "ค่าที่รู้ว่า optimal" กับ "BKS ที่ยังไม่พิสูจน์" ออกจากกัน ตอนนี้ `reference_bks.json` มีช่อง `bks_is_proven_optimal` เตรียมไว้แล้ว
