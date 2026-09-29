# Phase 11 — Dashboard / Prototype (Loop 10) ✅

สถานะ **PASS** (2026-09-28) · ใช้ Streamlit + Plotly ตาม skill.md §35 · โค้ดอยู่ที่ [readymix/dashboard/](../readymix/dashboard/)

> **คำถามของ Loop 10:** คนที่ไม่รู้ CVRP ดู demo แล้วเข้าใจไหมว่า AI เปลี่ยนการตัดสินใจอะไร และทำไม โดยไม่ต้องอ่านโค้ด

## วิธีเปิด

```bash
pip install -r readymix/requirements.txt
streamlit run readymix/dashboard/app.py
```

เลือก scenario, วันประเมิน (fresh day 9101–9110) และเวลาปัจจุบันที่ sidebar แล้วกด **Re-optimize** เพื่อรัน optimizer ใหม่ทั้งวัน (ใช้เวลาประมาณ 2 วินาที)

## หน้าจอ

| ส่วน | แสดงอะไร | skill.md §32 |
|---|---|---|
| KPI 7 ตัว | AFTER (AI) พร้อมลูกศรว่าต่างจาก BEFORE (แผนเดิม) ในวันเดียวกันเท่าไร: รถรอ, ไซต์ว่าง, on-time, น้ำมัน, CO₂, THB, เที่ยวที่ส่งไม่ได้ | Waiting, Distance, CO₂ |
| สถานะ ณ ตอนนี้ | แผนที่ plant/ไซต์/รถ ณ เวลาที่เลือก · Alerts (ไซต์ที่ AI คาดว่าจะช้า, รถที่รอเกิน 15 นาที) · Fleet status · ตาราง planned เทียบ AI predicted เทียบ actual | Current Time, Fleet/Site Status, Planned vs AI Ready, Delay Risk, Alerts |
| Timeline รถ | Gantt รถ 15 คัน AFTER และ BEFORE (แดง = รถรอที่ไซต์) | Current Routes |
| ทำไม AI ตัดสินใจแบบนี้ | ทุกการปล่อยรถพร้อมเหตุผลในรูปแบบ §33: เวลาที่ AI คาดว่าไซต์พร้อม, delay probability, confidence, fallback, เป้าเวลาถึง | Recommended Dispatch, decision trace |
| หลักฐาน 10 วัน | gate ของ Phase 9 และตาราง comparisons ของ Phase 10 เพื่อไม่ให้ดูเหมือนเลือกวันมาโชว์ | — |

ตัวอย่าง decision trace (S3, day 9101): *07:05 ปล่อย T015 ไป S008 · AI คาดว่าไซต์พร้อม 07:47 (delay prob 0.28, confidence 0.75) → ตั้งเป้าให้ถึง 07:42 (safety buffer 5 นาที)*

Screenshots: [สถานะ ณ ตอนนี้](dash_live.png) · [ทำไม AI ตัดสินใจ](dash_trace.png) · [Timeline](dash_timeline.png)

## ความน่าเชื่อถือ

- Dashboard **รันสด** ไม่ได้อ่านตัวเลขที่เก็บไว้ แล้วเช็กว่า log ตรงกับ run ประเมินของ Phase 9 ทุก byte และแสดงผลการเช็กบนหน้าจอ
- `TracingPredictor` แค่บันทึก output ของ `site_ready_v3` ไม่ได้แก้ policy · ไม่แตะไฟล์ที่ล็อกไว้ใน Phase 8/9
- Replay ไม่โชว์ข้อมูลอนาคต: เวลาไซต์พร้อมจริงจะแสดงหลังเวลานั้นผ่านไปแล้วเท่านั้น และ prediction ที่แสดงคือตัวล่าสุดที่มีอยู่ ณ เวลานั้น (มี test)
- ตัวเลข THB/CO₂ มาจาก `readymix/application/impact.py` และ `impact.yaml` ชุดเดียวกับ Phase 10
- มีป้าย SIMULATED บนหน้าจอเสมอ

## Gate

| Gate | ผล |
|---|---|
| Demo end-to-end ได้โดยไม่ต้องอธิบายโค้ด (เลือกวัน → ดูสถานะ → เห็นเหตุผล → เทียบก่อน/หลัง) | PASS: ตรวจด้วย Playwright screenshot 3 tab |
| ไม่ crash เมื่อเปลี่ยน scenario (รวม S6), เลื่อนเวลาไปช่วงเย็น, กด Re-optimize | PASS: Streamlit AppTest |
| ตัวเลขบนหน้าจอ trace กลับไปที่ run และไฟล์ผลได้ | PASS: hash ตรงกับ Phase 9 |

Tests: `python -m pytest readymix/tests` → **112 passed** (เพิ่ม 5 ข้อใน `test_loop10_dashboard.py`)

## ข้อควรรู้ตอนเดโม

- ไม่ใช่ทุกวันที่ AI ชนะ: เมื่อเทียบด้วย operational score C ดีกว่าแผนเดิม 79/90 วัน-scenario ส่วนที่แพ้หนักคือ S6 (งานล้นรถ) และ S7 บางวัน
- ค่าเริ่มต้น (S3, day 9101) เป็นวันที่รถรอลดลง แต่ on-time ต่ำกว่าแผนเดิม 11 จุด ถ้าจะเลือกวันอื่นมาเดโม **ต้องเปิด tab "หลักฐาน 10 วัน" ด้วยทุกครั้ง** เพื่อไม่ให้เป็นการเลือกวันมาโชว์
- "Re-optimize" คือรัน optimizer ทั้งวันใหม่ใน simulator ยังไม่ได้ต่อกับข้อมูลเวลาจริง
- แผนที่ใช้พิกัดจำลองที่วาดบนแกน lat/lon ธรรมดา ไม่ใช้ map tiles และเส้นทางรถเป็นเส้นตรงเพื่อแสดงตำแหน่งโดยประมาณ

## ส่งต่อ

- Phase 12 Stress Test: ใช้ `run_traced` ทดสอบกรณีรถเสีย, ข้อมูลหาย, demand +50% ต่อได้
- Phase 13 Slide: ใช้ screenshot ในโฟลเดอร์นี้ และตัวเลขจาก `phase10_carbon_business/*.csv` เท่านั้น
