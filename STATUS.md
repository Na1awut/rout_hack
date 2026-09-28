# Status

อัปเดตล่าสุด: 2026-09-28 · แผนเต็มอยู่ที่ [PLAN.md](PLAN.md)

**รูปแบบโฟลเดอร์:** แต่ละเฟสอยู่ใน `05_core_development/phaseN_<ชื่อ>/` ข้างในมีโค้ดของเฟสนั้น และไฟล์ `PHASEN.md` สรุปผล

| # | Phase | สถานะ | โฟลเดอร์ / หมายเหตุ |
|---|---|---|---|
| 0 | Scope / Technical Spec v0.1 | ⬜ | ยังไม่ได้เขียน scope 1 หน้า (input/output ถูกกำหนดไว้ใน config ของ Phase 1 แล้ว) |
| 1 | Freeze Core Algorithm | ✅ | [phase1_freeze/](phase1_freeze/PHASE1.md) · CORE-CVRP v1.0 · freeze_id `80b726c457a8` · Gap 0.00% ครบ 4 instance, รันซ้ำได้ผลเดิมทั้งตอนเครื่องว่างและตอนโหลด |
| 2 | Benchmark Runner | ✅ | [phase2_benchmark_infra/](phase2_benchmark_infra/PHASE2.md) · `.sol` reader + batch runner ผ่านครบ 7 acceptance criteria, freeze_id ตรงกับ Phase 1 เป๊ะ (ไม่ได้ fork solver) |
| 3 | Sanity Test | ✅ | [phase3_sanity_test/](phase3_sanity_test/PHASE3.md) · 5 เคสคำนวณด้วยมือตรงเป๊ะ + 2 เคส INFEASIBLE ถูกต้อง ตรวจซ้ำด้วยโค้ดอิสระที่ไม่พึ่ง validator.py |
| 4 | CVRPLIB Benchmark | ✅ | [phase4_cvrplib_benchmark/](phase4_cvrplib_benchmark/PHASE4.md) · 24 instance จริงจาก CVRPLIB (E+X series, 21-935 จุด) · solution_limit=2000 ใช้ได้จริงถึง ~150 จุด · เจอ non-determinism จริงตอน time_cap · **4/24** instance หาคำตอบแรกไม่เจอ (แก้จาก 3 เป็น 4 ระหว่าง Phase 5) |
| 5 | วินิจฉัย + ปิดจุดอ่อน → **CORE-CVRP v1.1** | ✅ | [phase5_weakness_fix/](phase5_weakness_fix/PHASE5.md) · freeze_id `bf63a542f2de` · PyVRP 0.14.0 **ILS** (config บันทึกผิดเป็น HGS) + หยุดตามจำนวนรอบ · 24/24 feasible, Gap เฉลี่ย 0.73%, สูงสุด 2.26% · Mission 2 ยัง 0.00% · บอกจำนวนรถที่ต้องใช้เมื่อฝูงรถไม่พอ |
| — | Loop 0 Regression Lock | ✅ | [phase6_readymix_simulation/loop_00_regression_lock/](phase6_readymix_simulation/loop_00_regression_lock/notes.md) · A/B/P-n40/P-n19 Gap 0.00% · route ตรง snapshot ทั้งการรันซ้ำและ process ใหม่ · gate จับการแก้ cost/route ได้ |
| 6 | Ready-Mix Problem & Simulation | ✅ | [phase6_readymix_simulation/](phase6_readymix_simulation/PHASE6.md) · Loop 1 simulator 9 scenario ผ่าน validator สร้างซ้ำได้ Core รับได้ · Loop 2 baseline A/R ผ่าน validator ทุกรอบ ตรงวันที่คำนวณด้วยมือ ไม่ใช้ข้อมูลอนาคต · 38 tests · **ข้อค้นพบ: ระยะทางตายตัว; ไม่มีการทำนายต้องเลือกรถรอหรือไซต์รอ; CO₂ จากเวลารอเป็นแค่ ≤5% ของน้ำมัน** |
| 7 | AI Site Readiness | ✅ Loop 3–4 PASS | [phase7_ai_readiness/PHASE7.md](phase7_ai_readiness/PHASE7.md) · site_ready_v3 · แก้ readiness revision ที่บวก history ซ้ำ · Fresh S8 MAE 10.006 → 9.248 นาที; normal mix 8.268 → 8.539 นาที · 88 tests PASS, runtime checks 46,819 predictions PASS, Core regression PASS |
| 8 | Predictive Dynamic Optimizer | ✅ | [phase8_dynamic_optimizer/PHASE8.md](phase8_dynamic_optimizer/PHASE8.md) · Loop 5–6 · gate ผ่าน 5/5 · รันซ้ำบน Linux ตรง 36/36 · AI+rolling ลดรถรอ 570→128 นาที แต่ไซต์ว่างเพิ่ม (แก้ใน Phase 9) |
| 9 | Baseline Comparison (Loop 7) | ✅ | [phase9_baseline_comparison/PHASE9.md](phase9_baseline_comparison/PHASE9.md) · iteration 01 FAIL → เพิ่ม safety buffer → iteration 02 PASS 5/5 บน fresh days 9101–9110 · C(AI) ดีกว่า B(no-AI) 218 นาที/วัน-scenario CI95 [117, 346] · ไม่นับ S6 ดีกว่าแผน static 15.2%; นับ S6 **เสมอ** · 104 tests · ⚠ freeze_id บน Linux ไม่ตรง แต่ route ตรง snapshot ต้องยืนยันบน Windows |
| 10 | Carbon + Business Impact (Loop 8) | ✅ | [phase10_carbon_business/PHASE10.md](phase10_carbon_business/PHASE10.md) · gate 4/4 · AI เทียบแผน static: −24 kgCO₂/วัน (−1.1%, ~7.2 t/ปี), −1,030 THB/วัน (−2.6%, ~309k THB/ปี), รถรอ −35% · คุณค่าหลักคือเวลา ไม่ใช่ CO₂ · ⚠ แหล่งอ้างอิงต้องเปิดยืนยันก่อนขึ้นสไลด์ |
| 11 | Dashboard / Prototype (Loop 10) | ✅ | [phase11_dashboard/PHASE11.md](phase11_dashboard/PHASE11.md) · `streamlit run readymix/dashboard/app.py` · BEFORE→AFTER, แผนที่, Gantt, decision trace §33, หลักฐาน 10 วัน · รันสดตรงกับ Phase 9 ทุก byte · 112 tests |
| 12 | Stress Test + Failure Cases (Loop 9) | ✅ | [phase12_stress_test/PHASE12.md](phase12_stress_test/PHASE12.md) · gate 5/5 · 105 stress run + 11 fault ไม่ crash · เจอ/แก้บั๊ก 2 ตัว · fleet check "ต้องเพิ่มรถ N คัน" ถูก 5/5 · **AI แพ้แผน static เมื่องานล้นกำลังรถ** (X1, X7) แต่ชนะชัดเมื่อไซต์วุ่น (−47%) |
| 13 | Slide / Video | ⬜ ขั้นถัดไป | |

Phase 6–7 รอบก่อน (หัวข้อ PrecastFlow) เก็บไว้ที่ [_archive/after_phase5_2026-09-28/](_archive/after_phase5_2026-09-28/) แผนใหม่มาจาก [idea.md](idea.md) · spec ระบบ [skill.md](skill.md) · วิธีทำงานแบบ loop และ gate [loop.md](loop.md) · โค้ดใหม่อยู่ใน `readymix/`
