# PourReady Live — ตัวสร้างข้อมูลสำหรับเว็บเล่นย้อน

`extract_sim.py` อ่าน log และ dataset จริงของ [phase9_baseline_comparison/iteration_02](../../phase9_baseline_comparison/iteration_02) (วันประเมิน 9101, ทั้ง 9 scenario × 3 policy: A_static_planned, B_dynamic_buffered, C_ai_rolling_buffered) แล้วแปลงเป็นไฟล์เดียว `sim_data.json` ที่หน้าเว็บโหลดไปเล่นย้อนรถวิ่งบนแผนที่แบบ real time

**ไม่มีการจำลองใหม่ — เป็นแค่การจัดรูปแบบข้อมูลจริงให้ browser อ่านง่าย:**
- ตำแหน่ง (x, y) แปลงจาก lat/lon จริงด้วย `readymix.simulation.common.planar_km` ตัวเดียวกับที่ solver ใช้
- เวลาที่รถแต่ละคันอยู่แต่ละช่วง (โหลด/วิ่ง/รอ/เท/ล้างถัง) มาจาก field ใน log ตรง ๆ (`load_start`, `depart`, `arrive`, `unload_start`, `unload_end`, `back`, `free`)
- ตัวเลข KPI สะสม (รถรอ, ไซต์ว่าง, ส่งแล้ว) คำนวณด้วยสูตรเดียวกับ `readymix/application/kpi.py` เพียงแต่แจกแจงเป็นเหตุการณ์ทีละจุดแทนที่จะสรุปครั้งเดียวตอนจบวัน — ผลรวมปลายวันจึงต้องตรงกับ `metrics.csv` เป๊ะ สคริปต์เช็กด้วย `assert` ทุกค่าก่อนเขียนไฟล์

## รันใหม่

```bash
export OMP_NUM_THREADS=1
python phase13_report/live_tool/extract_sim.py
```

ต้องมี `phase9_baseline_comparison/iteration_02/logs/` และ `.../datasets/*_world42_day9101/` อยู่ครบก่อน (ไม่ได้ commit เข้า git เพราะเป็นไฟล์ผลการรันจำนวนมาก — ดู `phase9_baseline_comparison/iteration_02/notes.md` วิธีรันใหม่)

Output: `sim_data.json` (~400 KB) — ไฟล์นี้คือไฟล์เดียวกับที่ publish คู่กับหน้าเว็บ [PourReady Live](https://claude.ai/artifact/9X7TpxptKBL7oB6GvC74pm)
