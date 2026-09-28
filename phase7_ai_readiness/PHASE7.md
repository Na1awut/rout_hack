# Phase 7 — AI Site Readiness ✅

อัปเดต 2026-09-28: **Loop 3 และ Loop 4 PASS**; พร้อมเริ่ม Phase 8 / Loop 5 โดยใช้ `site_ready_v3`

## สิ่งที่แก้ใน Loop 4

สาเหตุหลักคือ fallback ปฏิบัติต่อ `SITE_READY_EARLY/LATE` เหมือน delay ที่ต้องบวกเพิ่ม ทั้งที่ event contract เดิมใช้ประกาศนี้แทน base delay การบวก historical mean ซ้ำจึงทำให้ทายผิด

Policy ใหม่ `event_history` ใช้ประกาศที่มาถึงแล้วเพื่อแทน prior ของไซต์ในสภาพอากาศแห้ง ส่วน `SITE_DELAY/PUMP_FAILURE` ยังบวกเพิ่มตามเดิม กรณีฝนตกยังใช้ historical fallback เพราะ weather delay ไม่ทราบแน่นอน ทั้งหมดใช้เฉพาะ runtime events ไม่อ่าน ground truth และไม่เปลี่ยน simulator

ยังบังคับ fallback เมื่อ confidence < 0.6, input ออกนอก training range หรือ model/runtime features เสีย Fallback คืน confidence 0 และ point interval placeholder ซึ่งไม่ใช่ calibrated interval

## ผลจาก fresh holdout หลังล็อก policy

| ชุดข้อมูล | AI เดี่ยว MAE | AI + fallback MAE | fallback rule เดี่ยว MAE |
|---|---:|---:|---:|
| Normal mix: 7001–7040 (40 วัน) | 8.2680 | 8.5392 | 10.7748 |
| S8: 8001–8020 (20 วัน) | 10.0059 | 9.2477 | 11.4147 |

หน่วยนาที; S8 ลด error จาก AI เดี่ยวประมาณ 7.58% แต่ normal mix แย่ลง 0.2712 นาที การแก้นี้ช่วย resilience ต่อ readiness revision ไม่ได้ทำให้ทุก scenario แม่นขึ้น

| Gate | ผล |
|---|---|
| G1 test interval coverage 0.75–0.85 | PASS: 0.8020 |
| G2 test confidence ECE ≤0.05 | PASS: 0.0279 |
| G3 confidence จัดลำดับ error ได้ | PASS: high 7.3235 vs low 16.7454 นาที |
| G4 test ชนะ fallback rule และ S8 ไม่แย่กว่า AI | PASS ตามตาราง |
| G5 output contract / batch-runtime parity | PASS: 46,819 predictions, 5,512 fallbacks |
| G6 regression | PASS: 88 tests, Loop 3 G1–G6 PASS, Core regression PASS |

Runtime verification ใช้ real estimators ประมวลผลเป็น batch ต่อวันแล้ว cache เฉพาะ numerical inference ทุกแถวยังผ่าน production predictor logic; เทียบกับ uncached calls เพิ่ม 120 รายการ ผลตรงกันทั้งหมด

## ความน่าเชื่อถือและข้อจำกัด

- เลือก rule บน validation เดิม + S8 development seeds 4001–4020 เท่านั้น ล็อก config/source/bundle hashes ก่อนเปิด holdout ใหม่
- เกณฑ์ G4 คงเดิม ผลที่ไม่ผ่านของ iteration 3–4 เก็บไว้ครบ
- Coverage/ECE ข้างบนเป็นของ AI ก่อน fallback; S8 raw AI coverage 0.7478 และ ECE 0.0790 ยังด้อยกว่า normal mix จึงห้ามอ้างว่าช่วงคาดการณ์ calibrated บนทุก distribution
- ประโยชน์ S8 มาจากการตีความประกาศให้ถูกต้อง ไม่ใช่ ML ที่แม่นขึ้น; simulator มี readiness revisions ที่ให้ข้อมูลมากกว่าสถานการณ์จริงบางแบบ
- ทุกข้อมูลเป็น SIMULATED ยังไม่พิสูจน์ logistics KPI, carbon impact หรือความแม่นโลกจริง
- identity, schedule, service estimate และ clock ต้อง valid; กรณีเสียให้ ValueError ส่วน runtime features/model failures fallback ได้
- Service model ยังคงใช้ estimate หลัง validation ชนะ ML; ไม่อ่าน previous actual unload ที่ยังไม่ทราบเวลาจบงาน

## ไฟล์และคำสั่ง

ค่าเริ่มต้น `SiteReadyPredictor()` ใช้ [site_ready_v3.joblib](../readymix/ai/models/site_ready_v3.joblib) รายละเอียดใน model_card_v3.json และ [snapshot](loop_04_ai_reliability/iteration_05/snapshot.json)

```powershell
$env:OMP_NUM_THREADS = '1'
$env:PYTEST_DEBUG_TEMPROOT = (Get-Location).Path
python -m pytest readymix/tests -q --tb=short --disable-warnings
python phase7_ai_readiness/loop_04_ai_reliability/run_loop04.py
python phase7_ai_readiness/loop_04_ai_reliability/verify_runtime_v3.py
python phase6_readymix_simulation/loop_00_regression_lock/regression_lock.py
```

- [Metrics](loop_04_ai_reliability/iteration_05/metrics.csv), [selection](loop_04_ai_reliability/iteration_05/selection.csv), [gates](loop_04_ai_reliability/iteration_05/gates.json)
- [Runtime checks](loop_04_ai_reliability/iteration_05/runtime_checks.json), [pytest log](loop_04_ai_reliability/iteration_05/pytest.log)
- [Loop 3 log](loop_03_ai_prediction/verification.log), [Core log](core_regression.log)

## ส่งต่อ Loop 5

ใช้ prediction contract เพื่อสร้าง effective time window / departure timing ใน application layer โดยไม่แก้ Core ทดสอบว่าการตัดสินใจเปลี่ยนได้จริงและ constraint valid ก่อนทดลอง logistics KPI ใน loop ถัดไป ต้องแยกการใช้ current announcements ออกจาก predictive value เมื่อตั้ง baseline A/B/C
