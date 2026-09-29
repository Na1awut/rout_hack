# PourReady — เว็บสรุปโครงการ (โค้ดต้นฉบับ)

ไฟล์ HTML แบบ standalone ไม่ต้องติดตั้งอะไร ไม่ต้องรัน server — เปิดได้ทันทีด้วยการดับเบิลคลิก หรือ deploy เป็น static site ก็ได้

| ไฟล์ | คืออะไร |
|---|---|
| [index.html](index.html) | หน้าเล่าเรื่องทั้งโครงการ 9 สต็อป (Problem → Scale) พร้อมกราฟและตัวเลขจริงทุกตัว |
| [live.html](live.html) | เล่นย้อนรถโม่คอนกรีต 15 คันบนแผนที่ เทียบวิธีเดิมกับ AI พร้อมกัน มีคำอธิบายแต่ละสถานการณ์ ปุ่ม "ดูผลลัพธ์" และตารางสรุปทุกสถานการณ์ว่าช่วยได้เท่าไร — ข้อมูลฝังอยู่ในไฟล์เดียว (~460 KB) ไม่ fetch จากที่อื่น |

ทั้งสองไฟล์ลิงก์ถึงกันแบบ relative (`live.html` ↔ `index.html`) ต้องอยู่โฟลเดอร์เดียวกัน

## เปิดดู

**วิธีที่ไวที่สุด:** ดับเบิลคลิก `index.html` เปิดด้วยเบราว์เซอร์ได้เลย (ต้องต่อเน็ตเพื่อโหลดฟอนต์ Google Fonts เท่านั้น ไม่มี dependency อื่น)

**หรือรันเซิร์ฟเวอร์เล็ก ๆ** (เผื่อเบราว์เซอร์บล็อกบางอย่างตอนเปิดจาก `file://`):
```bash
cd phase13_report/site
python3 -m http.server 8000
# เปิด http://localhost:8000
```

**หรือขึ้น GitHub Pages ให้มีลิงก์สาธารณะ** — ไปที่ repo Settings → Pages → Build and deployment → Source: Deploy from a branch → เลือก branch นี้ + โฟลเดอร์ `/phase13_report/site` (หรือ `/root` ถ้าย้ายไฟล์ไปไว้ที่ `docs/`) จะได้ลิงก์แบบ `https://<user>.github.io/<repo>/` ให้กรรมการเปิดดูได้โดยไม่ต้อง clone
> ⚠ GitHub Pages ทำให้เนื้อหาเป็น**สาธารณะ** แม้ repo จะ private ก็ตาม — เปิดเฉพาะตอนพร้อมให้คนนอกทีมเห็นแล้วเท่านั้น

## ที่มาของข้อมูลใน live.html

ข้อมูลรถ/ไซต์/เวลาที่ฝังอยู่ใน `live.html` สร้างจาก [phase13_report/live_tool/extract_sim.py](../live_tool/extract_sim.py) ซึ่งอ่าน log จริงจาก [phase9_baseline_comparison/iteration_02](../../phase9_baseline_comparison/iteration_02) — รายละเอียดและวิธีสร้างใหม่อยู่ที่ [phase13_report/live_tool/README.md](../live_tool/README.md)

## ถ้าจะแก้ไข

ทั้งสองไฟล์เขียนด้วย HTML/CSS/JS ล้วน ไม่มี build step — แก้ตรงไฟล์แล้วรีเฟรชเบราว์เซอร์ได้เลย ยกเว้น `live.html` ที่สร้างจาก `phase13_report/live_tool/live_template.html` ด้วย `build_site.py` — แก้ที่ template แล้ว build ใหม่

สำเนาเดิมของทั้งสองหน้ายังเผยแพร่อยู่ที่ Claude Artifacts (ดูลิงก์ใน [REPORT.md](../REPORT.md) ภาคผนวก ข) — ไฟล์ในโฟลเดอร์นี้คือซอร์สโค้ดชุดเดียวกัน เก็บไว้ให้ทีมแก้ไขและ deploy เองได้โดยไม่ต้องพึ่ง Claude
