# Samaj App

| Folder | What it is | Stack | Runs on |
|---|---|---|---|
| [backend/](backend/) | API for everything | FastAPI + PostgreSQL + Alembic | http://localhost:8000 |
| [web-frontend/](web-frontend/) | Super Admin and City Admin panels | React + Vite | http://localhost:5173 |
| [app-frontend/](app-frontend/) | Member mobile app | Expo (React Native) | Expo Go / emulator |
| [docs/](docs/) | PRD, SRS, DDD, wireframes, DB schema | — | — |

Start the **backend first**; both frontends call it.

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- PostgreSQL 14+ running locally
- For the mobile app: the **Expo Go** app on your phone, or an Android emulator / iOS simulator

---

## 1. Backend (`backend/`)

### Setup (once)

```powershell
cd backend
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Create the database:

```sql
CREATE DATABASE samaj;
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/samaj

# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=<generated>

# python -c "import secrets; print(secrets.token_hex(32))"
# Do not change it once members exist — it orphans every stored mobile hash.
MOBILE_PEPPER=<generated>

# Dev switches (see "Dev switches" below)
ADMIN_MFA=false
OTP_BYPASS=true
```

Create the tables and the first Super Admin:

```powershell
alembic upgrade head
python create_super_admin.py     # prompts for name, email, password (min 12 chars)
```

### Run

```powershell
cd backend
venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- Health check: http://localhost:8000/health
- API docs (Swagger): http://localhost:8000/docs

`--host 0.0.0.0` is needed so a phone on the same Wi-Fi can reach the API.

### Tests

```powershell
pytest
```

### Dev switches

| Variable | Default | Effect |
|---|---|---|
| `ADMIN_MFA` | `true` | `false` = admin login is email + password only (no authenticator code). |
| `OTP_BYPASS` | `false` | `true` = member OTP accepts **any 6-digit code** (no SMS gateway yet). **Never enable in production.** |

---

## 2. Admin panels (`web-frontend/`)

### Setup (once)

```powershell
cd web-frontend
npm install
```

### Run

```powershell
npm run dev
```

Open http://localhost:5173 — it links to both panels. Vite proxies API calls to `http://localhost:8000`, so no CORS setup or `.env` is needed.

| Panel | URL | Who logs in | How the account is created |
|---|---|---|---|
| Super Admin | http://localhost:5173/super-admin/ | Super Admin | `python create_super_admin.py` (backend) |
| City Admin | http://localhost:5173/city-admin/ | City Admin of one city | Super Admin creates a city, then a City Admin for it, from the Super Admin panel |

Keep the trailing `/` in the panel URLs.

**Login:** email + password. If `ADMIN_MFA=true`, the first login asks you to enrol an authenticator app (Google Authenticator etc.), and later logins ask for its 6-digit code. A Super Admin can reset a City Admin's password or MFA from the Super Admin panel.

### Production build

```powershell
npm run build      # output in web-frontend/dist/
npm run preview    # serve the build locally
```

In production, serve `dist/` and route `/admin/`, `/superadmin/`, `/cityadmin/` and `/media/` to the backend from the same domain (the API has no CORS).

---

## 3. Member mobile app (`app-frontend/`)

### Setup (once)

```powershell
cd app-frontend
npm install
```

Create `app-frontend/.env` with the backend URL the app should call:

```env
# Phone on the same Wi-Fi: your PC's LAN IP (run `ipconfig`, look for IPv4 Address)
EXPO_PUBLIC_API_URL=http://192.168.x.x:8000
# Android emulator instead:
# EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
```

Restart Expo after changing `.env`.

### Run

```powershell
npm start          # then scan the QR code with Expo Go (Android) or the Camera app (iOS)
npm run android    # Android emulator
npm run ios        # iOS simulator (macOS only)
```

If the phone can't connect: check both devices are on the same Wi-Fi, the backend runs with `--host 0.0.0.0`, and Windows Firewall allows port 8000. `npx expo start --tunnel` helps on restrictive networks for the Expo connection (the API URL must still be reachable).

### Member login flow

1. Member signs up in the app with their mobile number and OTP (any 6 digits when `OTP_BYPASS=true`).
2. Their registration waits for approval by the **City Admin** of their city (City Admin panel).
3. Once approved, the member has full access to the app.

---

## Quick start (every day)

Three terminals:

```powershell
# 1
cd backend; venv\Scripts\activate; uvicorn main:app --reload --host 0.0.0.0 --port 8000
# 2
cd web-frontend; npm run dev
# 3
cd app-frontend; npm run android 
```

After pulling new code, run `alembic upgrade head` in `backend/` and `npm install` in any frontend whose `package.json` changed.
