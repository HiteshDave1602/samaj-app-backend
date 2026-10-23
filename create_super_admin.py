"""One-time bootstrap: python create_super_admin.py  (then log in via /admin/auth/login and enrol MFA)."""
from getpass import getpass

from sqlalchemy import select

from core.database import SessionLocal
from core.security import hash_password
from superadmin.city_admin.model import AdminUser

with SessionLocal() as db:
    if db.scalar(select(AdminUser.admin_id).where(AdminUser.role == "SUPER_ADMIN")):
        raise SystemExit("A Super Admin already exists.")
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip()
    password = getpass("Password (min 12 chars): ")
    if len(password) < 12 or password != getpass("Repeat password: "):
        raise SystemExit("Password too short or mismatch.")
    db.add(AdminUser(role="SUPER_ADMIN", full_name=full_name, email=email, password_hash=hash_password(password)))
    db.commit()
    print(f"Super Admin {email} created.")



 