# แผนพัฒนา Core CVRP → Hackathon

ใช้ CVRP เป็นแกนกลาง แล้วต่อยอดเป็นระบบ **AI + Ready-Mix dispatch** โดยไม่แตะ Core ที่ freeze แล้ว (แผนใหม่ของ Phase 6 เป็นต้นไปมาจาก [idea.md](idea.md))
เป้าหมายสุดท้ายคือต้องมีครบทุกอย่างนี้:

- หลักฐานว่า algorithm แข็งจริง
- use case ที่ impact สูง
- ตัวเลข carbon/business
- prototype
- slide พร้อมแข่ง

ดูความคืบหน้าล่าสุดได้ที่ [STATUS.md](STATUS.md)

## Roadmap หลัก

```text
── Solver Foundation ✅ ───────────────
[1] Freeze Core Algorithm
      ↓
[2] Build CVRP Benchmark Engine
      ↓
[3] Sanity / Correctness Test
      ↓
[4] CVRPLIB Benchmark
      ↓
[5] วิเคราะห์ + ปิดจุดอ่อน → CORE-CVRP v1.1
      ↓
    Regression Lock
── AI + Ready-Mix Application ─────────
[6] Ready-Mix Problem & Simulation
      ↓
[7] AI Site Readiness
      ↓
[8] Predictive Dynamic Optimizer
── Validation + Impact + Product ──────
[9]  Baseline Comparison
      ↓
[10] Carbon + Business Impact
      ↓
[11] Dashboard / Prototype
      ↓
[12] Stress Test + Failure Cases
      ↓
[13] Slide / Video
```

## Phase ↔ Engineering Loop

ตั้งแต่ Phase 6 ทำงานเป็น loop ตาม [loop.md](loop.md) (Define → Build Minimal → Test → Measure → Compare → Gate → Freeze) โดยใช้ spec จาก [skill.md](skill.md) แต่ละ Phase มีโฟลเดอร์ `phaseN_<ชื่อ>/` พร้อมรายงาน `PHASEN.md` และแต่ละ loop อยู่ใน `phaseN_<ชื่อ>/loop_NN_<ชื่อ>/` (config.yaml, metrics.csv, notes.md) ส่วนโค้ดที่ใช้ร่วมกันทุก phase อยู่ใน `readymix/`

| Phase | Loop |
|---|---|
| ก่อน 6 | 0 Regression Lock |
| 6 Ready-Mix Problem & Simulation | 1 Simulation · 2 Non-AI Baseline |
| 7 AI Site Readiness | 3 AI Prediction v1 · 4 AI Reliability |
| 8 Predictive Dynamic Optimizer | 5 Extended Optimizer · 6 Rolling Re-optimization |
| 9 Baseline Comparison | 7 AI vs No-AI (A Static / B Dynamic / C AI) |
| 10 Carbon + Business Impact | 8 Carbon + Business |
| 11 Dashboard / Prototype | 10 Product Prototype (เริ่มได้เมื่อ Loop 7 พิสูจน์ว่า AI ช่วยจริง) |
| 12 Stress Test + Failure Cases | 9 Stress / Failure |
| 13 Slide / Video | 11 Final Evidence · 12 Presentation |

## กติกา Architecture (ใช้ตั้งแต่ Phase 6)

```text
MODE = benchmark   → .vrp → Parser → CVRP Core (frozen) → Solution
MODE = readymix    → Ready-Mix Data → AI Prediction → Application Layer
                     (prediction → constraints/costs) → Extended Solver → Dispatch Plan
```

- **Core ห้ามโดน AI:** benchmark mode ต้องไม่มี AI / traffic / site readiness เข้ามาเกี่ยว เพราะนั่นคือหลักฐานว่า solver แก้ CVRP มาตรฐานได้จริง
- **เพิ่ม interface ได้ แต่ห้ามแก้ algorithm เดิม:** สร้างของใหม่แยกไฟล์ เช่น `solve_dynamic(instance, time_windows, service_times, ready_probabilities, departure_times)` ใน `extended_solver.py` ถ้า Extended Solver พัง Benchmark ก็ยังไม่พังตาม
- **AI ไม่ได้มาแทน algorithm:** AI ตอบว่า "solver ต้อง optimize จากข้อมูลอะไร" เช่น Predicted Ready 09:42 (delay 87%) → Application Layer แปลงเป็น Effective Time Window 09:35–10:30 แล้วค่อยส่งเข้า optimizer ตัว solver ไม่จำเป็นต้องรู้ว่าตัวเลขมาจาก AI

---

## Phase 0 — กำหนดกติกาของโปรเจกต์

| สิ่ง | รายละเอียด |
|---|---|
| เป้าหมาย | ทีมเข้าใจตรงกันว่าอะไรคือ Core และอะไรจะเพิ่มทีหลัง |
| ต้องทำ | เขียน scope 1 หน้า |
| ข้อมูลที่ต้องมี | algorithm ปัจจุบันแก้อะไรได้, input/output, constraint ที่รองรับ |
| Output | Technical Spec v0.1 |

**Input**

```text
Depot
Customer coordinates
Demand
Vehicle capacity
Number of vehicles
```

**Output**

```text
Route 1: Depot → A → B → C → Depot
Route 2: Depot → D → F → Depot

Total distance = xxx
```

> **ห้ามใส่ Carbon / Traffic / EV / Time Window ในขั้นนี้**
> algorithm รุ่นแรกต้องเป็น Pure CVRP เพื่อใช้เป็น benchmark engine → เรียกว่า `CORE-CVRP`

---

## Phase 1 — Freeze Core Algorithm

ล็อก version ของ algorithm ที่มีตอนนี้ เช่น `Optimizer Core v1.0`
ห้ามแก้ระหว่าง benchmark เพราะถ้า algorithm เปลี่ยนตลอด เราจะไม่รู้ว่าผลดีขึ้นเพราะอะไร

**บันทึก:** algorithm name, version, random seed, hyperparameters, stopping criteria, hardware, programming language

```text
ตัวอย่าง
Population = 100      CPU    = Ryzen 5
Iterations = 500      RAM    = 16 GB
Mutation   = 0.05     Python = 3.11
Local Search = 2-opt
```

ถ้า algorithm มี randomness (GA, Ant Colony, SA, randomized search) ให้กำหนด seed หลายค่า (`seed = 1 … 10`) เพื่อทดสอบหลายรอบ

**Output:** `algorithm_config.yaml` หรือ `.json`

---

## Phase 2 — สร้าง Benchmark Engine

ขั้นนี้**ยังไม่ใช่การแข่ง algorithm** แต่เป็นการสร้างสนามสอบ

```text
Load CVRP instance → Run Algorithm → Validate solution
  → Calculate objective → Compare BKS → Save result
```

- อ่าน `.vrp` / `.sol` แล้วดึง coordinates, demand, capacity, depot, vehicles, BKS
- คำนวณ: Total Distance, Runtime, Vehicle Count, Capacity Violation, Missing Customer, Duplicate Customer, Gap %

$$Gap = \frac{OurSolution - BKS}{BKS} \times 100$$

**Output:** CSV

```text
instance,size,bks,our_best,our_avg,gap,runtime,feasible
A-n32-k5,31,784,790,794,0.77,0.42,true
```

---

## Phase 3 — Sanity Test

พิสูจน์ก่อนว่า algorithm **ทำถูกจริง** ด้วย instance เล็กมาก (5 / 10 / 20 / 30 customers)

ต้องตรวจ:

- customer ทุกจุดถูกเยี่ยมครั้งเดียว
- Load ≤ Capacity
- route เริ่มและจบที่ depot
- total distance ถูกต้อง

ใช้ instance ที่คำนวณด้วยมือได้ เช่น `Depot=(0,0), A=(1,0), B=(2,0), C=(3,0)`

> algorithm ที่ให้ distance สวย แต่ customer หาย 1 จุด = **ใช้ไม่ได้**

---

## Phase 4 — CVRPLIB Benchmark จริง

| Level | Customers | จุดประสงค์ |
|---|---:|---|
| Tiny | <50 | correctness |
| Small | 50–100 | คุณภาพ solution |
| Medium | 100–250 | quality + speed |
| Large | 250–500 | scalability |
| Stress | 500–1,000 | enterprise scale |

เริ่มที่ประมาณ 20–30 instance ก่อน

- เก็บต่อ instance: best, average, worst, std, average runtime, best runtime, feasible %
- ถ้า algorithm เป็นแบบสุ่ม ให้รันอย่างน้อย 10 รอบต่อ instance (ถ้ามีเวลา 20–30 รอบ)
- **กราฟ:** Instance Size vs Runtime, Instance Size vs Gap, Gap Distribution, Best/Avg/Worst

---

## Phase 5 — วิเคราะห์ "บุคลิก" ของ Algorithm

คำถามไม่ใช่แค่ว่า "algorithm ดีไหม" แต่คือ **"มันเก่งเรื่องอะไร"**

- ขยายขนาดแล้ว Gap ต่ำและเร็ว → scaling ดี เหมาะกับองค์กรใหญ่
- Gap ต่ำ แต่ 500 nodes ใช้ 2 นาที → เหมาะกับ strategic/nightly planning มากกว่า dynamic routing
- clustered ดีมาก แต่ random ปานกลาง → เหมาะกับ retail / urban / distribution center มากกว่า rural

**Output:** `Algorithm Strength Profile` (Strength / Weakness)

---

## ก่อนเริ่ม Phase 6 — Regression Lock

เก็บ snapshot ของ benchmark mode ไว้ก่อนเพิ่ม AI เข้าระบบ

```text
A-n32-k5
B-n31-k5
P-n40-k5
```

- เก็บ: output routes, objective, version ของ engine (**PyVRP 0.14.0** สำหรับ v1.1 ส่วน OR-Tools ใช้เฉพาะรัน v1.0 เป็น baseline), config/freeze_id และ benchmark result
- หลังจากนี้ ถ้าผลของ benchmark mode เปลี่ยนโดยไม่ได้ตั้งใจ ต้องรู้ทันที

**Output:** snapshot + สคริปต์ตรวจเทียบที่รันซ้ำได้

---

## Phase 6 — Ready-Mix Problem & Simulation

นิยามปัญหาจัดส่งคอนกรีตผสมเสร็จ (Ready-Mix) และสร้างข้อมูลจำลองที่ solver รับได้

- นิยาม: site, truck, demand, planned time, actual readiness, traffic, disruption
- แหล่งข้อมูล:
  1. **Public Data:** coordinates, road network, distance, travel time
  2. **Simulated Operational Data:** ต้องเขียนชัดว่า *Synthetic operational dataset* ห้ามเรียกว่าข้อมูลจริง
  3. **Real Business Assumption:** fuel consumption, diesel price, CO₂ factor, driver cost, vehicle capacity → อิงแหล่งข้อมูลจริงเสมอ
- simulator ต้องสร้างทั้ง **planned** และ **actual** readiness เพื่อใช้วัด AI ใน Phase 7

**Output:** Dataset + simulator ที่ solver รับได้

---

## Phase 7 — AI Site Readiness

สถานะตรวจรับล่าสุด (2026-09-28): **Loop 3–4 PASS / site_ready_v3** แก้ service feature leakage และแก้ fallback ให้เคารพ readiness revision ที่แทนค่า history; G4 ผ่านบน fresh holdout โดยไม่ลดเกณฑ์ พร้อม Loop 5 ดูผลและข้อจำกัดใน [PHASE7.md](phase7_ai_readiness/PHASE7.md)

สร้าง ML ทำนาย `ready_time`, `delay_probability`, `service_time`, `confidence`

ต้องตอบคำถามกรรมการได้ว่า *"AI ดีกว่าใช้ scheduled time ยังไง?"* จึงต้องมี baseline:

| | ใช้ข้อมูล |
|---|---|
| Baseline | Planned Ready Time |
| AI | Predicted Ready Time |

**วัดความแม่นของ prediction:** Ready-time MAE, delay prediction accuracy, calibration / confidence

**วัดผลต่อ logistics (สำคัญกว่า):** `Planned data → Solver` เทียบกับ `AI data → Solver` บน Truck Waiting, Site Waiting, Distance, On-time %, Fuel, CO₂, Fleet utilization

> ถ้า AI แม่นขึ้น แต่ logistics KPI ไม่ดีขึ้น แปลว่า AI **ไม่มี business value**

**Output:** AI model ที่วัด accuracy และผลต่อ KPI ได้จริง

---

## Phase 8 — Predictive Dynamic Optimizer

เอาผล AI เข้า Extended CVRP + เลือกเวลาออกเดินทาง + rolling re-optimization

```text
08:00  สร้างแผนทั้งวัน
09:10  Site B เริ่ม delay → AI predicts: Ready at 10:05
       → Optimizer พบว่าแผนเดิมไม่คุ้ม → Re-optimize รถที่เหลือ
         Truck 7 → Site C · Truck 8 → delay departure · Truck 9 → Site B later
ทุก 15–30 นาที: Update State → Predict Again → Optimize Again
```

- เป็น **Rolling Horizon Optimization** ตัวเชื่อม AI กับ Routing
- อย่าเริ่มจาก weighted multi-objective ที่ซับซ้อน ให้ใช้ objective เดียว แล้วที่เหลือทำเป็น constraint:

$$\min\ Cost \quad \text{s.t.} \quad Load \le Capacity,\ Arrival \in EffectiveTimeWindow$$

- โครงไฟล์ (Core เดิมไม่แตะ):

```text
core_solver.py          ← Frozen
extended_solver.py      ← Ready-Mix
dynamic_dispatch.py
ai_predictor.py
simulation.py
```

**Output:** ระบบเต็ม `AI → Decision → Route`

---

## Phase 9 — Baseline Comparison

สถานะ (2026-09-28): **PASS** · ผลและข้อจำกัดใน [PHASE9.md](phase9_baseline_comparison/PHASE9.md) · ใน V1 route ของทุกวิธีเหมือนกัน (Phase 6) จึงเทียบที่เวลาปล่อยรถ A static / B dynamic / C AI

ห้ามโชว์ตัวเลขเดี่ยวๆ ที่ไม่มี context ต้องเทียบกับ baseline อย่างน้อย 3 ตัว:

1. Naive / current planning (planned time, ไม่ re-optimize)
2. Nearest Neighbor
3. Standard CVRP / OR-Tools

| Method | Distance | CO₂ | Cost | Waiting | On-time % | Runtime |
|---|---:|---:|---:|---:|---:|---:|
| Manual | | | | | | — |
| Nearest | | | | | | |
| Standard CVRP | | | | | | |
| Ours (AI + Dynamic) | | | | | | |

---

## Phase 10 — Carbon + Business Impact

สถานะ (2026-09-28): **PASS** · ผลใน [PHASE10.md](phase10_carbon_business/PHASE10.md) · ค่าอ้างอิงใน `readymix/config/impact.yaml`

$$CO_2 = Distance \times FuelConsumption \times EmissionFactor$$

แบบดีขึ้น: $Fuel = f(Distance, Load, Traffic, Idle)$ (Ready-Mix มีเวลารถรอที่ไซต์ซึ่งกินน้ำมัน)
รายงานเป็น kgCO₂/trip, /order, /month

$$Savings = Fuel + Labor + Vehicle + Maintenance$$

แปลงเป็นตัวเลขที่ธุรกิจเข้าใจ → **THB/year, tCO₂e/year, hours/year**

ข้อมูลที่ต้องมี: vehicle type, fuel type, fuel consumption, emission factor, distance, load, idle time

---

## Phase 11 — Dashboard / Prototype

สถานะ (2026-09-28): **PASS** · [PHASE11.md](phase11_dashboard/PHASE11.md) · `streamlit run readymix/dashboard/app.py`

ทำ **Decision Support Dashboard**: BEFORE → กด OPTIMIZE → AFTER
แสดงแผนที่เส้นทางของรถแต่ละคัน, prediction ของแต่ละไซต์, และ KPI (↓Distance, ↓CO₂, ↓Cost, ↓Waiting, ↑On-time, ↑Utilization)

---

## Phase 12 — Stress Test + Failure Cases

- **Scenario:** Normal / Peak Demand / Vehicle Shortage / High Fuel Price / หลายไซต์ delay พร้อมกัน / AI ทำนายผิด และหลายขนาดโจทย์ เพื่อพิสูจน์ว่าไม่ได้เลือกเคสมาโชว์
- **ทำให้ระบบพังเอง:** demand เกิน fleet capacity, ไซต์ที่ไปไม่ถึง, รถเสีย, demand พุ่ง +50%, ข้อมูลขาด
- ระบบต้องตอบว่า "No feasible solution" หรือ "ต้องเพิ่มรถอีก 2 คัน" **ห้าม crash**
- ทุกครั้งต้องรัน Regression Lock ว่า benchmark mode ยังได้ผลเดิม

---

## Phase 13 — Slide / Video

**Data pack** — ทุกตัวเลขบน slide ต้องมาจากไฟล์เหล่านี้ **ห้ามพิมพ์เลขเองบน slide**

```text
benchmark_results.csv      carbon_results.csv
algorithm_config.json      baseline_comparison.csv
ai_accuracy.csv            scenario_results.csv
business_simulation.csv
```

**Story (9 หน้า)**

```text
01 Problem
02 Why Current Routing Is Not Enough
03 Our Insight
04 Solution
05 How Algorithm Works
06 CVRP Benchmark
07 Real-world Simulation
08 Business + Carbon Impact
09 Scale / Implementation
```

เริ่มจาก pain ก่อน แล้วค่อยใช้ benchmark พิสูจน์ว่า engine ทำงานได้จริง อย่าเปิดด้วย benchmark

---

## ลำดับงานตอนนี้

1. ~~Phase 1–5: Solver Foundation~~ ✅ (CORE-CVRP v1.1, freeze_id `bf63a542f2de`)
2. ~~Loop 0 Regression Lock~~ ✅ ([notes](phase6_readymix_simulation/loop_00_regression_lock/notes.md))
3. ~~Phase 6 Ready-Mix Problem & Simulation~~ ✅ ([PHASE6.md](phase6_readymix_simulation/PHASE6.md): Loop 1 Simulation, Loop 2 Non-AI Baseline)
4. ~~Phase 7 AI Site Readiness (Loop 3–4)~~ ✅ ([PHASE7.md](phase7_ai_readiness/PHASE7.md))
5. ~~Phase 8 Predictive Dynamic Optimizer (Loop 5–6)~~ ✅ ([PHASE8.md](phase8_dynamic_optimizer/PHASE8.md))
6. ~~Phase 9 Baseline Comparison (Loop 7)~~ ✅ ([PHASE9.md](phase9_baseline_comparison/PHASE9.md): iteration 02 PASS)
7. ~~Phase 10 Carbon + Business Impact (Loop 8)~~ ✅ ([PHASE10.md](phase10_carbon_business/PHASE10.md))
8. ~~Phase 11 Dashboard / Prototype (Loop 10)~~ ✅ ([PHASE11.md](phase11_dashboard/PHASE11.md))
9. **Phase 12 Stress Test + Failure Cases (Loop 9)** ← ขั้นถัดไป

**ไม่ย้อนกลับไปแก้ Core และไม่รื้อ Phase เก่า**
