import os
from django.core.exceptions import ValidationError
from PIL import Image

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_SIZE = 5 * 1024 * 1024

def validate_image(file):
    # Already-saved files were validated when uploaded; only check new uploads.
    if getattr(file, "_committed", False):
        return
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("รับเฉพาะไฟล์ JPG, JPEG หรือ PNG")
    if file.size > MAX_SIZE:
        raise ValidationError("ขนาดไฟล์ต้องไม่เกิน 5 MB")
    try:
        file.seek(0)
        with Image.open(file) as img:
            img.verify()
    except Exception:
        raise ValidationError("ไฟล์ที่อัปโหลดไม่ถูกต้อง")
    finally:
        file.seek(0)