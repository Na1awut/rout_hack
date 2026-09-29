# Mission 2 — Benchmark & Solver · PourReady

ZIP นี้มี 2 ส่วน: (1) Solver ที่แก้ 3 Benchmark และ (2) กรณีที่สร้างเอง: ระบบจัดส่งคอนกรีตผสมเสร็จ PourReady (AI + Optimizer) ทุกผลลัพธ์รันซ้ำได้ด้วยคำสั่งเดียว และสคริปต์ตรวจเองว่าตรงกับหลักฐานที่บันทึกไว้

## ผลลัพธ์ Benchmark

| Instance | Optimal reference | คำตอบของเรา | Gap | รถที่ใช้ | ผ่าน validator |
|---|---:|---:|---:|---:|---|
| A-n32-k5 | 784 | **784** | 0.00% | 5/5 | ✅ |
| B-n31-k5 | 672 | **672** | 0.00% | 5/5 | ✅ |
| P-n40-k5 | 458 | **458** | 0.00% | 5/5 | ✅ |

Routes อยู่ใน `results/benchmark/<instance>.sol` (รูปแบบ CVRPLIB: เลขลูกค้า = node id − 1, ไม่แสดง depot) และ `results/benchmark/summary.csv`

## ติดตั้ง

ต้องใช้ Python 3.11 (ทดสอบบน 3.11.15, Linux x86_64)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

| Library | Version | ใช้ทำอะไร |
|---|---|---|
| pyvrp | **0.14.0** (บังคับ — solver ปฏิเสธเวอร์ชันอื่น) | engine ของ CVRP solver |
| scikit-learn | **1.9.0** (บังคับ — โมเดล AI ถูก save ด้วยเวอร์ชันนี้) | โมเดลทำนายเวลาไซต์พร้อม |
| numpy / pandas / joblib / PyYAML | 2.4.6 / 3.0.6 / 1.6.0 / 6.0.1 | ข้อมูลและ config |
| streamlit / plotly | 1.64.0 / 7.1.0 | dashboard (ไม่จำเป็นสำหรับรันผล) |

## 1) รัน Benchmark

```bash
python run_benchmark.py
```

ใช้เวลาไม่ถึง 10 วินาที พิมพ์ cost, gap, routes ของทั้ง 3 โจทย์ แล้วเขียน `results/benchmark/`

**Parameter และ seed** (จาก `phase5_weakness_fix/algorithm_config.json`):

| ค่า | เท่ากับ |
|---|---|
| Algorithm | CORE-CVRP v1.1 บน PyVRP 0.14.0 (`Model.solve` = Iterated Local Search) |
| Random seed | **1** |
| เกณฑ์หยุด | ไม่ดีขึ้น 5,000 รอบติด หรือครบ 50,000 รอบ (นับรอบ ไม่นับวินาที → ผลเหมือนกันทุกเครื่อง) |
| ระยะทาง | EUC_2D ปัดเศษ `floor(sqrt(dx²+dy²)+0.5)` |
| จำนวนรถ | 5 คันต่อโจทย์ (`phase1_freeze/reference_bks.json`) |

สคริปต์เทียบ route fingerprint กับ snapshot ที่ล็อกไว้ใน `phase6_readymix_simulation/loop_00_regression_lock/snapshot.json` ถ้าไม่ตรงจะ exit code 1

## 2) รันกรณีที่สร้างเอง: PourReady

```bash
python run_pourready.py            # สถานการณ์ S4 หลายไซต์ล่าช้า วัน 9101 (~10 วินาที)
python run_pourready.py --all      # ครบ 9 สถานการณ์ วัน 9101 (~1 นาที)
python run_pourready.py --scenario S6_high_demand --day 9105
```

แต่ละรอบจะ:
1. สร้างวันจำลองใหม่จาก seed (`world_seed = 42`, `day seed = 9101`) ด้วย config ใน `readymix/config/`
2. รัน 3 ระบบในวันเดียวกัน: **A** แผนตายตัว · **B** ปรับแผนไม่มี AI · **C** AI + Optimizer (ระบบของเรา)
3. ตรวจว่าแผนที่รันทำได้จริงทางกายภาพ (`execution_validator`)
4. เขียน KPI, ต้นทุน (บาท), CO₂ และตารางเส้นทางรถรายเที่ยว (`*_routes.csv`: รถคันไหน ไปไซต์ไหน ออก/ถึง/เท/กลับกี่โมง)
5. ถ้าเป็นวันประเมิน 9101–9110 จะเทียบ sha256 ของ log กับผลที่บันทึกใน `phase9_baseline_comparison/iteration_02/metrics.csv` ต้องตรงทุก byte

**Parameter** (`phase9_baseline_comparison/iteration_02/config.json`, `selection.json`): step 5 นาที · AI ทำนายใหม่ทุก 15 นาที · เวลาเผื่อ C = 5 นาที (คันแรก) / 15 นาที (คันถัดไป), B = 0 / 10 นาที (เลือกจากวันทดลอง 6001–6010 ก่อนเปิดวันประเมิน) · โมเดล `readymix/ai/models/site_ready_v3.joblib`

## ผลลัพธ์ที่อยู่ใน ZIP

| ไฟล์ | คืออะไร |
|---|---|
| `results/benchmark/` | ผลและ routes ของ 3 โจทย์ + log การรัน |
| `results/pourready/summary.csv` | KPI ของ 9 สถานการณ์ × 3 ระบบ วัน 9101 (27/27 ตรงกับ Phase 9) |
| `results/pourready/*_routes.csv`, `*_log.json` | เส้นทางรถรายเที่ยวของทุกการรัน |
| `results/pourready/datasets/` | ข้อมูลวันจำลองที่สร้างจาก seed (สร้างใหม่ได้ทุกครั้ง) |
| `phase9_baseline_comparison/iteration_02/` | หลักฐานหลัก 450 run (10 วัน × 9 สถานการณ์ × 5 ระบบ), gate ผ่าน 5/5 |
| `phase10_carbon_business/` | ต้นทุน บาท / CO₂ และช่วงความเชื่อมั่น |
| `phase13_report/REPORT.md` | รายงานสรุปทั้งโครงการ |
| `phase13_report/site/index.html`, `live.html` | เว็บสรุปผล และเว็บเล่นย้อนรถวิ่ง (เปิดด้วยเบราว์เซอร์ได้เลย) |

**ผลหลักของ PourReady** (ค่าเฉลี่ย 10 วันประเมินใหม่ × 9 สถานการณ์, ระบบ C เทียบ A):
- เวลารถรอลดลง 35%
- ต้นทุนที่วัดได้ลดลงราว 1,030 บาทต่อวัน
- ดีกว่าวิธีเดิมใน 8 จาก 9 สถานการณ์
- แพ้ในวันงานล้นรถ (S6)

ข้อมูลปฏิบัติการทั้งหมดเป็น **ข้อมูลจำลอง** ส่วนตัวคูณบาท/CO₂ มาจากแหล่งสาธารณะใน `readymix/config/impact.yaml`

## โครงสร้าง

```text
run_benchmark.py              ← Mission 2: 3 benchmarks
run_pourready.py              ← กรณีที่สร้างเอง
phase1_freeze/benchmarks/     ← A-n32-k5.vrp, B-n31-k5.vrp, P-n40-k5.vrp
phase5_weakness_fix/          ← CVRP solver (core_v1_1/) + config + freeze tooling
readymix/                     ← PourReady: simulation, ai (โมเดล v3), application (optimizer), dashboard
```

Dashboard เพิ่มเติม (ใช้ข้อมูล 90 วันใน `phase9_baseline_comparison/iteration_02/datasets/`): `streamlit run readymix/dashboard/app.py`

ZIP นี้ไม่มี `.venv`, `node_modules` หรือข้อมูลลับ repo เต็ม (ทุก phase, 117 tests) อยู่ที่ branch `claude/sleepy-cerf-s70yp8`
