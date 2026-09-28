# Loop 0 — Regression Lock ✅ PASS

2026-09-28 · CORE-CVRP v1.1 · freeze_id `bf63a542f2de` · PyVRP 0.14.0 (ILS)

## 1. Define

**Hypothesis:** benchmark mode ของ Core v1.1 ให้ objective และ route เดิมทุกครั้งบนโจทย์ Mission 2

**Gate (จาก [config.yaml](config.yaml)):** freeze_id และ PyVRP version ต้องตรง, validator ผ่าน, Gap 0.00%, รันซ้ำ 2 ครั้งต้องได้ route และจำนวนรอบเท่ากัน, และต้องตรงกับ snapshot ส่วน runtime บันทึกไว้เฉยๆ ไม่ใช้ตัดสิน เพราะขึ้นกับเครื่อง

## 2. Build Minimal

- [readymix/core/frozen_core.py](../../readymix/core/frozen_core.py): ช่องทางเดียวที่ `readymix/` ใช้ import Core ไม่แก้ solver ใดๆ แค่ชี้ไปที่ `phase5_weakness_fix/core_v1_1/` และมี `check_freeze()` ที่หยุดทำงานทันทีถ้า freeze_id เปลี่ยน
- [regression_lock.py](regression_lock.py): `--snapshot` เขียน lock แค่ครั้งเดียว (ถ้ามีไฟล์อยู่แล้วจะไม่ยอมเขียนทับ) ถ้าไม่ใส่ flag จะตรวจเทียบกับ snapshot

## 3–4. Test

| กรณีทดสอบ | ผลที่คาด | ผลจริง |
|---|---|---|
| snapshot ครั้งแรก (รัน 2 ครั้งต่อโจทย์) | PASS | ✅ PASS |
| verify ใน process ใหม่ | PASS | ✅ PASS |
| สั่ง `--snapshot` ซ้ำ | ไม่ยอมเขียนทับ | ✅ REFUSED |
| แก้ cost ใน snapshot | FAIL | ✅ จับได้ |
| สลับลำดับ 2 จุดใน route เดียว | FAIL | ✅ จับได้ |
| run 2 ได้ route ต่างจาก run 1 | FAIL | ✅ จับได้ |
| Gap ไม่เป็น 0 / validator ไม่ผ่าน | FAIL | ✅ จับได้ |

## 5. Measure — [snapshot.json](snapshot.json) · [metrics.csv](metrics.csv)

| โจทย์ | Cost | BKS | Gap | รถ | รอบ | fingerprint | เวลา (ข้อมูลเท่านั้น) |
|---|---:|---:|---:|---:|---:|---|---:|
| A-n32-k5 | 784 | 784 | 0.00% | 5 | 5,021 | `2b402097367d` | 1.2 s |
| B-n31-k5 | 672 | 672 | 0.00% | 5 | 5,033 | `5b982d6b66b6` | 1.2 s |
| P-n40-k5 | 458 | 458 | 0.00% | 5 | 5,011 | `a06c3cb461cc` | 1.7–2.0 s |
| P-n19-k2 | 212 | 212 | 0.00% | 2 | 5,005 | `53f733cfddcd` | 0.5 s |

## 6. Compare

Cost ตรงกับ Gate 1 ของ `phase5_weakness_fix/verify_v1_1.py` และตรงกับ BKS ที่พิสูจน์แล้วว่า optimal ทั้ง 4 โจทย์

## 7. Decision Gate — **PASS → Freeze**

## 8. Version Snapshot

- snapshot เก็บ freeze_id, PyVRP version, SHA-256 ของ `algorithm_config.json` และ `reference_bks.json`, route ครบทุกเส้น พร้อม load และระยะของแต่ละเส้น
- โฟลเดอร์นี้**ไม่มี git** จึงยังทำ git tag ตาม loop.md ไม่ได้ ถ้าจะใช้ git ภายหลัง ควร tag ที่จุดนี้

## วิธีใช้ใน loop ถัดไป

```text
python phase6_readymix_simulation/loop_00_regression_lock/regression_lock.py
```

รันทุกครั้งก่อนปิด loop ถ้าได้ FAIL แปลว่า benchmark mode เปลี่ยน ต้องหยุดหาสาเหตุก่อน ห้ามเขียน snapshot ใหม่เพื่อให้ผ่าน

## ขอบเขตของหลักฐานนี้

ทดสอบบนเครื่องเดียว (AMD64, 12 threads, Python 3.14.6) และตอนเครื่องว่าง ผลตอน CPU โหลดหนักอ้างอิงจาก E5 ของ Phase 5 ซึ่งทดสอบถึง 458 จุด ยังไม่ใช่หลักฐานว่าได้ผลเหมือนกันทุกเครื่อง
