import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_image(value):
    """Validate an uploaded image: jpg/jpeg/png, at most 5 MB, real image."""
    if not isinstance(value, UploadedFile):
        raise ValidationError('ไฟล์ที่อัปโหลดไม่ถูกต้อง')

    name = (value.name or '').lower()
    if not any(name.endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS):
        raise ValidationError('รองรับเฉพาะไฟล์รูปภาพนามสกุล .jpg, .jpeg หรือ .png เท่านั้น')

    if value.size > MAX_IMAGE_SIZE:
        raise ValidationError('ขนาดไฟล์ต้องไม่เกิน 5 MB')

    try:
        value.seek(0)
        with Image.open(value) as image:
            image.verify()
        value.seek(0)
    except Exception:
        raise ValidationError('ไฟล์รูปภาพเสียหายหรือไม่ใช่รูปภาพที่ถูกต้อง')
