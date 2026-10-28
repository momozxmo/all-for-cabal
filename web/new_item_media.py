"""Local image validation only; never upload, transform or reuse another tool's image.

Pillow API: https://pillow.readthedocs.io/en/stable/reference/Image.html
Restrict decoding formats before identification; never load EPS/JP2/other plugins.
"""
from io import BytesIO
import warnings

MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_TYPES = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}


class ImageDecoderUnavailable(RuntimeError):
    pass


def validate_image(content, declared_type):
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError('รูปต้องมีข้อมูลและไม่เกิน 5 MB')
    try:
        import PIL
        from PIL import Image
        version = tuple(int(part) for part in PIL.__version__.split('.')[:2])
        if version < (13, 0):
            raise ImageDecoderUnavailable('ต้องใช้ตัวตรวจรูป Pillow 13.0 ขึ้นไป')
    except (ImportError, ValueError):
        raise ImageDecoderUnavailable('ตัวตรวจรูปยังไม่พร้อมใช้งาน') from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content), formats=list(ALLOWED_TYPES)) as picture:
                kind, size = picture.format, picture.size
                if (kind not in ALLOWED_TYPES or size[0] <= 0 or size[1] <= 0 or
                        size[0] * size[1] > MAX_IMAGE_PIXELS or getattr(picture, 'n_frames', 1) != 1):
                    raise ValueError('unsupported image dimensions or animation')
                picture.verify()
            with Image.open(BytesIO(content), formats=[kind]) as picture:
                picture.load()
        media_type = ALLOWED_TYPES[kind]
        if str(declared_type or '').lower().split(';', 1)[0] != media_type:
            raise ValueError('MIME mismatch')
        return {'media_type': media_type, 'width': size[0], 'height': size[1], 'size': len(content)}
    except Exception:
        raise ValueError('ใช้รูป PNG/JPEG/WebP แบบภาพนิ่งที่อ่านได้ ไม่เกิน 20 ล้านพิกเซล และชนิดไฟล์ต้องตรงกัน') from None
