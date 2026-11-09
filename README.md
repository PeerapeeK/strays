# ระบบหาบ้านและคัดกรองเจ้าของให้สุนัขจรจัด (Stray Dog Adoption System)

ระบบจัดการการรับอุปการะสุนัขจรจัดครบวงจร ตั้งแต่การลงทะเบียนสุนัข การจองคิวสัมภาษณ์
การคัดกรองผู้รับอุปการะ การทำสัญญา การติดตามผลหลังการรับอุปการะ ไปจนถึงรายงานสถิติ
และบันทึกการใช้งาน (audit log)

## เทคโนโลยีที่ใช้

- Django 5/6 (โปรเจกต์ `config`, แอปเดียว `core`)
- SQLite
- Bootstrap 5 (CDN)
- Chart.js (CDN) สำหรับรายงาน
- `django-simple-history` สำหรับ audit log
- Argon2 สำหรับ hash รหัสผ่าน
- Pillow สำหรับตรวจสอบรูปภาพ
- requests สำหรับส่ง push notification

## การติดตั้ง

```powershell
# 1) สร้างและเปิดใช้งาน virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) ติดตั้งแพ็กเกจ
pip install django django-simple-history argon2-cffi pillow requests

# 3) สร้างฐานข้อมูล
python manage.py migrate

# 4) สร้างข้อมูลตัวอย่าง (บัญชีทดลอง + สุนัขตัวอย่าง)
python manage.py seed_demo

# 5) เริ่มเซิร์ฟเวอร์
python manage.py runserver
```

เปิดเว็บที่ <http://127.0.0.1:8000/>

## บัญชีทดลอง (Demo accounts)

สร้างด้วยคำสั่ง `python manage.py seed_demo` — รหัสผ่านทุกบัญชีคือ `demo1234`

| บทบาท | ชื่อผู้ใช้ | รหัสผ่าน |
| --- | --- | --- |
| ผู้ดูแลระบบ (Admin) | `admin` | `demo1234` |
| เจ้าหน้าที่ (Staff) | `staff1` | `demo1234` |
| เจ้าหน้าที่ (Staff) | `staff2` | `demo1234` |
| ผู้รับอุปการะ (Adopter) | `adopter1` | `demo1234` |
| ผู้รับอุปการะ (Adopter) | `adopter2` | `demo1234` |
| ผู้รับอุปการะ (Adopter) | `adopter3` | `demo1234` |

## Push notifications

ระบบส่ง push notification ผ่าน `core/push.py`

- ตั้งค่า `PUSH_PROVIDER_URL` ใน `config/settings.py` เพื่อเปิดใช้งานการส่งจริง
  (HTTP POST, timeout 10 วินาที)
- ถ้า `PUSH_PROVIDER_URL` ว่าง ระบบจะทำงานใน **โหมดพัฒนา (dev mode)** และถือว่าส่งสำเร็จ
  โดยไม่เรียกผู้ให้บริการภายนอก
- ความพยายามทั้งหมด 4 ครั้ง (1 ครั้งแรก + retry อีก 3 ครั้ง) หลังจากนั้นสถานะเป็น `failed`
- ความล่าช้าระหว่าง retry เพิ่มขึ้นแบบ exponential (`PUSH_RETRY_DELAY`)

คำสั่งที่เกี่ยวข้อง:

```powershell
# ส่งรายการที่ถึงกำหนดหนึ่งรอบ
python manage.py send_notifications

# ทำงานต่อเนื่องทุก 15 วินาที
python manage.py send_notifications --loop --interval 15

# สร้าง/อัปเดตการแจ้งเตือนล่วงหน้า และทำเครื่องหมายการติดตามผลที่เกินกำหนด
python manage.py queue_reminders
python manage.py queue_reminders --days 3
```

`queue_reminders` ใช้ `dedupe_key` เพื่อป้องกันการแจ้งเตือนซ้ำ และจะเปลี่ยนสถานะ
การติดตามผลที่เลยกำหนดเป็น `overdue`

## รายงานสถิติ

- **รายงานการรับอุปการะ** `/reports/adoption-stats/`
- **รายงานการติดตามผล** `/reports/followup-stats/`

ทั้งสองหน้ามีตัวกรองช่วงวันที่ ตารางข้อมูล กราฟ Chart.js และปุ่มส่งออก CSV
เจ้าหน้าที่ (Staff) และผู้ดูแลระบบ (Admin) เข้าใช้งานได้ โดยผู้ดูแลระบบสามารถ
ตรวจสอบรายงานได้เช่นกัน

## Audit log

หน้า `/audit-log/` (เฉพาะ Admin) แสดงประวัติการเปลี่ยนแปลงข้อมูลทุกโมเดลธุรกิจ
จาก `django-simple-history` พร้อมตัวกรองวันที่ โมเดล และประเภทการกระทำ

## การทดสอบ

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py check
python manage.py test
```

ชุดทดสอบประกอบด้วย smoke test ที่ล็อกอินด้วยทุกบทบาทและเรียกทุก URL
รวมถึงการทดสอบ push retry (mock HTTP) และการป้องกันการแจ้งเตือนซ้ำของ
`queue_reminders`
