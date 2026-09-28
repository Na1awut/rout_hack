# Loop 4 — PASS (2026-09-28)

Iteration 5 แก้ความหมาย event: SITE_READY_EARLY/LATE แทน prior delay ไม่ใช่เพิ่มเข้า historical mean ส่วน SITE_DELAY/PUMP_FAILURE ยังเป็น additive ใช้ข้อมูลเฉพาะที่ประกาศแล้ว บังคับ low-confidence/OOD fallback เช่นเดิม

เลือก `event_history` บน normal validation + S8 development แล้วล็อกก่อนเปิด fresh test 7001–7040 / fresh S8 8001–8020 G1–G4 PASS; S8 AI MAE 10.0059 → combined 9.2477 นาที Normal mix 8.2680 → 8.5392 นาที ยังมี tradeoff

G5 ตรวจ production predictor 46,819 แถว (inference cache จาก real models; uncached parity 120 แถว) PASS G6: 88 tests PASS, Loop 3 PASS, Core regression PASS

Default model คือ site_ready_v3; ไม่เขียนทับ v1/v2 และไม่ลบหลักฐาน iteration ที่ไม่ผ่าน Snapshot/model card บันทึก provenance และข้อจำกัด

ใช้ run_loop04.py หรือ run_loop04_v3.py --evaluate และ verify_runtime_v3.py รายละเอียด [PHASE7.md](../PHASE7.md) ผลเก่า metrics.csv ที่อยู่ระดับโฟลเดอร์นี้เป็น legacy เท่านั้น ผลปัจจุบัน [iteration_05/metrics.csv](iteration_05/metrics.csv)
