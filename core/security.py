import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

from cryptography.fernet import Fernet

from core.config import settings

# Encrypts TOTP secrets and member PII (mobile, address) at rest; also seals tickets and member access tokens.
fernet = Fernet(settings.fernet_key)

# scrypt (stdlib): n=2**14, r=8, p=1 is the OWASP-recommended minimum.
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=_N, r=_R, p=_P)
    return hmac.compare_digest(candidate.hex(), digest)


# TOTP (RFC 6238): SHA-1, 30 s step, 6 digits -- what Google Authenticator & co. expect.
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def totp(secret_b32: str, at: float | None = None) -> str:
    counter = int((time.time() if at is None else at) // 30)
    mac = hmac.new(base64.b32decode(secret_b32), struct.pack(">Q", counter), "sha1").digest()
    offset = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def verify_totp(secret_b32: str, code: str) -> bool:
    # +/- one step tolerates phone clock drift.
    now = time.time()
    return any(hmac.compare_digest(totp(secret_b32, now + d * 30), code) for d in (-1, 0, 1))


if __name__ == "__main__":  # self-check, from backend/: python -m core.security
    h = hash_password("correct horse")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)
    assert h != hash_password("correct horse")  # salted

    rfc_secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp(rfc_secret, at=59) == "287082"  # RFC 6238 test vector (last 6 digits)
    assert totp(rfc_secret, at=1111111109) == "081804"
    s = new_totp_secret()
    assert verify_totp(s, totp(s))
    assert not verify_totp(s, totp(s, time.time() - 120))  # 4 steps old
    print("ok")
