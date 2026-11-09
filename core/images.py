from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image

PROFILE_PHOTO_SIZE = 400


def process_profile_photo(uploaded_file):
    """Convert an uploaded image to a centred 400x400 RGB JPEG."""
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as image:
        image = image.convert('RGB')
        width, height = image.size
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        image = image.resize(
            (PROFILE_PHOTO_SIZE, PROFILE_PHOTO_SIZE),
            Image.Resampling.LANCZOS,
        )
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=90)

    return ContentFile(
        buffer.getvalue(), name=f'profile-{uuid4().hex}.jpg'
    )


def delete_stored_file(field_file):
    """Delete a file from storage, ignoring missing files."""
    if not field_file:
        return
    try:
        field_file.storage.delete(field_file.name)
    except Exception:
        pass
