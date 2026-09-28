# Phase 6 — หลักฐานและขอบเขตข้อกล่าวอ้าง

ตรวจวันที่ 2026-09-28 ใช้ข้อมูลผู้ผลิต ผู้จัด ไลบรารี และงานวิจัยต้นฉบับ แหล่งอ้างอิงใน `idea.md` ที่เป็น `chatgpt-content-reference` ไม่ใช่ citation ที่ตรวจย้อนกลับได้ เอกสารนี้แทนที่เฉพาะข้อกล่าวอ้างที่ใช้ตัดสินหัวข้อ

## แหล่งหลัก

| ID | แหล่ง | ยืนยันอะไร | ขอบเขต |
|---|---|---|---|
| S1 | [CPAC Extra Precast — ผู้ผลิต](https://cpac.co.th/th/product/detail/cpac-precast-concrete-system) | มีระบบสินค้าจริง ครอบคลุมผนัง พื้น บันได คาน ถาดห้องน้ำและงานตามแบบ | ไม่ยืนยันความถี่ของปัญหาขนส่งหรือข้อมูลคำสั่งซื้อของ CPAC |
| S2 | [ใบข้อมูล CPAC Extra Precast](https://cdn.cpac.co.th/uploads/Leaflet_CPAC_Extra_Precast_Concrete_System_965ac22a05.pdf) — [สำเนาที่ดาวน์โหลด](evidence/cpac_extra_precast.pdf) | หน้า 2 ระบุผนังและพื้นหนา 100/120/150 mm และสั่งพิเศษ 170/200 mm; หน้า 3 กล่าวถึง BIM และการประสานขนส่ง/ติดตั้ง | ความกว้าง ความยาว น้ำหนักรถ/ชิ้นงานใน probe เป็นสมมติฐาน ไม่ได้มีในใบข้อมูลนี้ |
| S3 | [Liu et al. (2020), Real-Time Optimization of Precast Concrete Component Transportation and Storage](https://onlinelibrary.wiley.com/doi/10.1155/2020/5714910) | ปัญหาการจัดส่ง จัดเก็บ และยกที่ไม่สัมพันธ์กับแผนก่อสร้างทำให้ย้ายชิ้นงานซ้ำ งานนี้ศึกษาการเชื่อมแผนกับสถานะงานจริง | ผลลดเวลา 37% เป็น on-site transportation ในกรณีศึกษาของผู้วิจัย ไม่ใช่ระยะทางถนน คาร์บอน หรือผลของเรา/CPAC |
| S4 | [CPAC 1 Click](https://web.cpac.co.th/th/1Click) | มีการเลือกสถานที่ ขนาดรถ วันเวลา และล็อกคิวรถโม่อยู่แล้ว | ไม่ได้พิสูจน์ว่าระบบนี้มีหรือไม่มี JIS optimization |
| S5 | [Smart Delivery — รายการแอปโดย SCG Cement-Building Materials](https://play.google.com/store/apps/details?id=com.scg.cpac.sda) | มีเครื่องมือจัดการและติดตามการส่ง ready-mix | ยืนยันขอบเขตจากคำอธิบายผู้พัฒนา ไม่ได้เข้าระบบภายใน |
| S6 | [SCGJWD — FMCG](https://www.scgjwd.com/en/services/industry/fmcg) | องค์กรใช้ route optimization และ real-time tracking ในบริการที่ระบุ | ไม่ใช่หลักฐานว่ากระบวนการ CPAC Precast เหมือนกัน |
| S7 | [PyVRP 0.14.0 API](https://pyvrp.readthedocs.io/en/stable/api/pyvrp.html) | รองรับ capacity, service-start windows, release time และ shifts; ตรวจ signature กับแพ็กเกจที่ติดตั้งแล้ว | `stable` เปลี่ยนได้ ใช้เวอร์ชัน local 0.14.0 เป็นฐานทดลอง; API นี้ไม่ได้ทำ arbitrary crane scheduling ให้เรา |
| S8 | [PyVRP benchmark notes](https://pyvrp.readthedocs.io/en/stable/setup/benchmarks.html) และ [โค้ด solve ที่ติดตั้ง](evidence/installed_pyvrp_solve.txt) | PyVRP เปลี่ยนจาก HGS เป็น ILS ตั้งแต่ 0.13.0; local `solve()` สร้าง `IteratedLocalSearch` | เป็นการแก้ชื่อ engine ในเอกสาร ไม่ได้เปลี่ยนผล benchmark เดิม |
| S9 | [สไลด์ผู้จัดใน workspace](../../src/03_Slide%20กิจกรรมเตรียมความพร้อม.pdf) | หน้า 30 อนุญาต optimization library และห้าม hard-code; หน้า 40–42 ให้สร้างกรณีจากบริบท SCG-CPAC แล้วแปลงเป็น CVRP พร้อม Context/Data/Constraints/Method/Result | อ่านจากภาพหน้าจริงใน PDF ไม่ใช้ข้อสรุปจาก `idea.md` เพียงอย่างเดียว |

ภาพที่ใช้ตรวจ: [ใบข้อมูลหน้า 2](evidence/cpac_extra_precast_2.png), [หน้า 3](evidence/cpac_extra_precast_3.png), [สไลด์หน้า 30](evidence/organizer_page_30.png), [หน้า 40](evidence/organizer_page_40.png), [หน้า 41](evidence/organizer_page_41.png), [หน้า 42](evidence/organizer_page_42.png)

เว็บอ่าน PDF ใบข้อมูลไม่ได้เพราะขนาดไฟล์ 12.85 MB จึงดาวน์โหลดจาก CDN ของ CPAC แล้วอ่านภาพทุกหน้าที่ใช้อ้างอิง สำเนาและ SHA-256 อยู่ใน [evidence_manifest.json](evidence/evidence_manifest.json)

## Product specification ที่ใช้จริงใน probe

| รายการ | ส่วนที่มีหลักฐานจาก S2 | ส่วนที่จำลอง | น้ำหนักที่คำนวณ |
|---|---|---|---:|
| ผนัง `wall_100` | ชนิดผนังและความหนา 100 mm | 2.8 × 2.4 m, ความหนาแน่นรวมสมมติ 2,400 kg/m³, แผ่นทึบไม่มีช่องเปิด | ceil(2.8 × 2.4 × 0.10 × 2,400) = 1,613 kg |
| พื้น `floor_120` | ชนิดพื้นและความหนา 120 mm | 3.0 × 1.2 m, ความหนาแน่นรวมสมมติ 2,400 kg/m³, แผ่นทึบ | ceil(3.0 × 1.2 × 0.12 × 2,400) = 1,037 kg |

นี่คือ 2 กลุ่มชิ้นงานที่อิงชนิดและความหนาจากผู้ผลิต พร้อมสมมติฐานมวลอย่างเปิดเผย ยังไม่ใช่ shop drawing หรือ packing list ของ CPAC น้ำหนักไม่ได้ใช้ตรวจความแข็งแรงโครงสร้างหรือรับรองการบรรทุกจริง ก่อนใช้กับงานจริงต้องแทนด้วยน้ำหนักและ load plan ที่ผู้รับผิดชอบอนุมัติ

## ข้อความใน idea.md ที่ต้องปรับก่อนนำเสนอ

- **S Wall 85–95 kg/m² และ Hollow Core 182 kg/m²:** เป็นสินค้า/รุ่นเฉพาะ ใช้แทนผนังทึบหรือพื้นทึบใน Extra Precast ไม่ได้ ลิงก์ PDF เก่าบางรายการ redirect ไปหน้าแรก จึงไม่ใช้ตัวเลขเหล่านี้ใน dataset รอบนี้
- **CVRP fit = 5 และ map ตรงตัว:** ต้องลดความมั่นใจ เพราะไซต์เดียวมีหลายครั้งส่ง หลายชิ้นงาน และคิวเครน ต้องใช้ node ระดับ delivery batch ไม่ใช่รวม demand ต่อไซต์ทั้งวัน
- **ความใหม่/โอกาสชนต่ำ:** พบงานเดิมเกี่ยวกับลำดับ การขนส่ง และการจัดเก็บแล้ว จุดต่างเป็นการประกอบระบบทดลองที่ตรวจสอบได้ ไม่ใช่การค้นพบ JIS หรือ VRP ใหม่ ยังไม่ทราบแนวคิดทีมอื่นและความสามารถระบบภายใน CPAC
- **ลดระยะทาง/รถ/CO₂ พร้อมกัน:** ยังไม่พิสูจน์ Phase 6 ได้ระยะทางและจำนวนรถเท่าเดิมเมื่อเพิ่มข้อจำกัด แต่แก้ความผิดลำดับในแผนได้
- **รถเปล่าปล่อยคาร์บอนเท่าเดิม:** ใช้เป็นข้อสรุปเชิงปริมาณไม่ได้ มวล ความเร็ว การเดินเบา และพฤติกรรมเครื่องยนต์ต้องเข้า emissions model
- **PyVRP HGS:** เวอร์ชัน 0.14.0 ที่ใช้จริงเป็น ILS ผล Phase 5 เดิมยังคงเดิม แต่ต้องเรียกชื่อ engine ให้ตรง
- **หาไม่เจอ = INFEASIBLE / รถที่ต้องใช้ขั้นต่ำ:** heuristic หาไม่เจอไม่ได้พิสูจน์ว่าไม่มีคำตอบ และจำนวนรถจาก elastic solve เป็นจำนวนในแผนที่หาได้ ไม่ใช่ค่าต่ำสุดที่พิสูจน์แล้ว Phase 6 ใช้ `NO_FEASIBLE_SOLUTION_FOUND` แยกจากกรณีที่มีข้อพิสูจน์เชิง capacity

## สถานะความมั่นใจ

- ยืนยันแล้ว: มีสินค้าและบริบทจริง, ปัญหามีหลักฐานในวรรณกรรม, รูปแบบ case ตรงข้อกำหนดที่อ่านจากสไลด์, สร้างข้อมูลจำลองและแก้แบบจำกัดขอบเขตได้
- เป็นข้อเสนอออกแบบ: batch หนึ่งมี 3 ชิ้น, ผู้วางแผนส่งลำดับและคิวเครนมาให้, รถประเภทเดียวที่อนุมัติให้บรรทุกได้, direct-to-crane delivery
- ยังไม่ยืนยัน: pain ของ CPAC รายไซต์, อัตราเกิดปัญหา, multi-stop ใช้จริงบ่อยแค่ไหน, ข้อจำกัดการวางซ้อน/รัดตรึง/เข้าถึงชิ้นงาน, road restrictions, fuel/idle factors, willingness to use/pay และ novelty เทียบระบบภายใน

สิ่งที่ยังไม่ยืนยันเป็นขอบเขตของการนำไปใช้จริงและการกล่าวอ้าง impact ไม่ใช่เหตุผลให้เรียกข้อมูลจำลองว่า operational data จริง
