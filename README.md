# ระบบหาบ้านและคัดกรองเจ้าของให้สุนัขจรจัด (Stray Dog Adoption System)

ระบบจัดการการรับอุปการะสุนัขจรจัดครบวงจร ตั้งแต่การลงทะเบียนสุนัข การจองคิวสัมภาษณ์
การคัดกรองผู้รับอุปการะ การทำสัญญา การติดตามผลหลังการรับอุปการะ ไปจนถึงรายงานสถิติ
และบันทึกการใช้งาน (audit log)

## เทคโนโลยีที่ใช้

- Python 3.13
- Django 6.1 (โปรเจกต์ `config`, แอปเดียว `core`)
- SQLite
- Bootstrap 5 (CDN) และ `static/css/theme.css`
- Chart.js (CDN) สำหรับรายงาน
- `django-simple-history` สำหรับ audit log
- Argon2 สำหรับ hash รหัสผ่าน
- Pillow สำหรับตรวจสอบรูปภาพ
- `requests` สำหรับส่ง push notification

## ฟีเจอร์หลัก

- **ผู้รับอุปการะ (Adopter):** สมัครสมาชิก/เข้าสู่ระบบ ค้นหาสุนัข จองคิวสัมภาษณ์
  ติดตามสถานะนัด ตรวจสอบสัญญา และส่งแบบฟอร์มติดตามผลพร้อมรูปถ่าย
- **เจ้าหน้าที่ (Staff):** จัดการข้อมูลสุนัข ตรวจสอบและยืนยัน/ปฏิเสธคำขอรับเลี้ยง
  บันทึกผลสัมภาษณ์ สร้างสัญญา นัดตรวจบ้าน และประเมินผลการติดตามผล
- **ผู้ดูแลระบบ (Admin):** จัดการบัญชีผู้ใช้ สร้างบัญชีเจ้าหน้าที่ ระงับบัญชี
  ดูรายงานสถิติ และตรวจสอบบันทึกการใช้งาน

บทบาทถูกกำหนดผ่าน Django Groups (`Adopter`, `Staff`, `Admin`) โดย superuser
นับเป็น Admin และผู้ที่สมัครผ่านหน้าเว็บจะได้บทบาท Adopter

## การติดตั้ง

```powershell
# 1) สร้างและเปิดใช้งาน virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) ติดตั้งแพ็กเกจ
pip install django django-simple-history argon2-cffi pillow requests

# 3) สร้างฐานข้อมูล
python manage.py migrate

# 4) สร้างบัญชีผู้ดูแลระบบ
python manage.py createsuperuser

# 5) เริ่มเซิร์ฟเวอร์
python manage.py runserver
```

เปิดเว็บที่ <http://127.0.0.1:8000/>

หมายเหตุ:

- ไฟล์อัปโหลด (รูปสุนัข รูปที่อยู่อาศัย ฯลฯ) ถูกเก็บใน `media/`
- รองรับเฉพาะรูป JPG, JPEG และ PNG ขนาดไม่เกิน 5 MB ต่อไฟล์
- ข้อมูลส่วนบุคคลจะถูกบันทึกหลังผู้ใช้ยินยอม PDPA เท่านั้น (เก็บ `pdpa_consent_at`)

## โครงสร้างโปรเจกต์

```text
config/                 การตั้งค่าโปรเจกต์ (settings, urls)
core/
  models.py             โมเดลธุรกิจทั้งหมด (Dog, InterviewRequest, Contract, FollowUp ฯลฯ)
  views.py              ฟังก์ชัน view ทั้งระบบ
  forms.py              Django ModelForm/Form พร้อม BootstrapFormMixin
  permissions.py        ตัวช่วยตรวจสอบบทบาท (Adopter/Staff/Admin)
  services.py           ตรรกะธุรกิจ (สัญญา การติดตามผล audit ฯลฯ)
  push.py               ตัวส่ง push notification พร้อม retry
  validators.py         ตัวตรวจสอบรูปภาพ
  templates/            เทมเพลต Bootstrap 5 (ข้อความ UI เป็นภาษาไทย)
  tests/                ชุดทดสอบทั้งหมด
static/css/theme.css    ธีมหลักของระบบ
docs/                   เอกสารความต้องการและ mockup
```

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
เจ้าหน้าที่ (Staff) และผู้ดูแลระบบ (Admin) เข้าใช้งานได้

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
รวมถึงการทดสอบสิทธิตามบทบาท การทดสอบปุ่มดำเนินการตามสถานะของคำขอรับเลี้ยง
การทดสอบ push retry (mock HTTP) และการป้องกันการแจ้งเตือนซ้ำของ `queue_reminders`
