import re
from pathlib import Path
from uuid import uuid4

from core.config import settings
from core.security import fernet

# Files only admins (or the owner) may read: ID documents, matrimony photos, import uploads.
# Encrypted at rest and returned only through endpoints that check access; nothing here is mounted.
# ponytail: local disk + Fernet. Swap for the private KMS-encrypted bucket (DDD) together with core/media.py.
PRIVATE_DIR = Path(settings.private_dir)
PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
KEY = re.compile(r"^[0-9a-f]{32}$")  # server-made keys only, so a key can never walk out of PRIVATE_DIR


def save(data: bytes) -> str:
    key = uuid4().hex
    (PRIVATE_DIR / key).write_bytes(fernet.encrypt(data))
    return key


def load(key: str) -> bytes | None:
    if not KEY.match(key) or not (PRIVATE_DIR / key).is_file():
        return None
    return fernet.decrypt((PRIVATE_DIR / key).read_bytes())


def delete(key: str):
    if KEY.match(key):
        (PRIVATE_DIR / key).unlink(missing_ok=True)
