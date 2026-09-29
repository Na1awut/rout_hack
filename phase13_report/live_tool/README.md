# PourReady Live — ตัวสร้างข้อมูลสำหรับเว็บเล่นย้อน

`extract_sim.py` อ่าน log และ dataset จริงของ [phase9_baseline_comparison/iteration_02](../../phase9_baseline_comparison/iteration_02) (วันประเมิน 9101, ทั้ง 9 scenario × 3 policy: A_static_planned, B_dynamic_buffered, C_ai_rolling_buffered) แล้วแปลงเป็นไฟล์เดียว `sim_data.json` ที่หน้าเว็บโหลดไปเล่นย้อนรถวิ่งบนแผนที่แบบ real time

**ไม่มีการจำลองใหม่ — เป็นแค่การจัดรูปแบบข้อมูลจริงให้ browser อ่านง่าย:**
- ตำแหน่ง (x, y) แปลงจาก lat/lon จริงด้วย `readymix.simulation.common.planar_km` ตัวเดียวกับที่ solver ใช้
- เวลาที่รถแต่ละคันอยู่แต่ละช่วง (โหลด/วิ่ง/รอ/เท/ล้างถัง) มาจาก field ใน log ตรง ๆ (`load_start`, `depart`, `arrive`, `unload_start`, `unload_end`, `back`, `free`)
- ตัวเลข KPI สะสม (รถรอ, ไซต์ว่าง, ส่งแล้ว) คำนวณด้วยสูตรเดียวกับ `readymix/application/kpi.py` เพียงแต่แจกแจงเป็นเหตุการณ์ทีละจุดแทนที่จะสรุปครั้งเดียวตอนจบวัน — ผลรวมปลายวันจึงต้องตรงกับ `metrics.csv` เป๊ะ สคริปต์เช็กด้วย `assert` ทุกค่าก่อนเขียนไฟล์

นอกจากข้อมูลการวิ่งแล้ว ยังใส่ผลลัพธ์ 2 ระดับให้หน้าเว็บใช้เทียบ: `day_result` (ผลของวัน 9101 ที่เล่นย้อนให้ดู) และ `avg10` (ค่าเฉลี่ย 10 วันทดสอบของแต่ละสถานการณ์) จาก `metrics.csv` ของ Phase 9 และต้นทุน/CO₂ จาก `phase10_carbon_business/impact_runs.csv` (กรณี value) ค่าเฉลี่ยรวมตรงกับ Phase 9 (score 1839.0 / 2052.9 / 1834.7)

## รันใหม่

```bash
export OMP_NUM_THREADS=1
python phase13_report/live_tool/extract_sim.py   # สร้าง sim_data.json
python phase13_report/live_tool/build_site.py    # สร้าง phase13_report/site/live.html จาก live_template.html
```

แก้หน้าตาเว็บที่ `live_template.html` แล้วรัน `build_site.py` อย่าแก้ `site/live.html` ตรง ๆ เพราะจะถูกเขียนทับ

อ่านจาก `phase9_baseline_comparison/iteration_02/logs/` และ `.../datasets/*_world42_day9101/` ซึ่งอยู่ใน git แล้ว ไม่ต้องรันการทดลองใหม่

Output: `sim_data.json` (~400 KB) — ไฟล์นี้คือไฟล์เดียวกับที่ publish คู่กับหน้าเว็บ [PourReady Live](https://claude.ai/artifact/9X7TpxptKBL7oB6GvC74pm)
