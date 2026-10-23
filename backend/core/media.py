import re
import struct
from pathlib import Path
from uuid import uuid4

from core.config import settings

# ponytail: local disk, served at /media. Swap for the private object-storage bucket + pre-signed URLs
# (DDD) before running more than one server.
MEDIA_DIR = Path(settings.media_dir)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 5 * 1024 * 1024
KEY = re.compile(r"^[0-9a-f]{32}\.(png|jpg)$")  # server-made keys only, so a key can never walk out of MEDIA_DIR


def image_info(data: bytes) -> tuple[str, int, int]:
    """(ext, width, height) from the PNG/JPEG header; ValueError for anything else."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 <= len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):  # SOFn frame header
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpg", w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError("Upload a JPEG or PNG image")


def save(data: bytes) -> tuple[str, int, int]:
    """Stores an image; returns (media_key, width, height)."""
    ext, w, h = image_info(data)
    key = f"{uuid4().hex}.{ext}"
    (MEDIA_DIR / key).write_bytes(data)
    return key, w, h


def dimensions(key: str) -> tuple[int, int] | None:
    """Width and height of a stored image; None if the key isn't one of ours."""
    if not KEY.match(key) or not (MEDIA_DIR / key).is_file():
        return None
    # ponytail: reads the whole file for its header; fine at 5 MB max.
    _, w, h = image_info((MEDIA_DIR / key).read_bytes())
    return w, h


def url(key: str | None) -> str | None:
    return f"/media/{key}" if key else None


def png(w: int, h: int) -> bytes:
    """Smallest header image_info accepts; for tests."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", w, h) + b"\x08\x02\x00\x00\x00"


if __name__ == "__main__":  # self-check, from backend/: python -m core.media
    assert image_info(png(1080, 1920)) == ("png", 1080, 1920)
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + bytes(9)
    sof0 = b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 1920, 1080) + bytes(10)
    assert image_info(b"\xff\xd8" + app0 + sof0) == ("jpg", 1080, 1920)
    for bad in (b"GIF89a" + bytes(20), b"", b"\xff\xd8\xff"):
        try:
            image_info(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    assert dimensions("../.env") is None and dimensions(f"{uuid4().hex}.png") is None
    print("ok")
