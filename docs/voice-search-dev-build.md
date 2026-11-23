# Testing voice search on your phone (Expo development build)

The Directory screen has a mic button that turns speech into search text. It uses `expo-speech-recognition`, which needs
native code that **Expo Go does not include**. So:

| How you open the app | What the mic does |
| --- | --- |
| **Expo Go** | Focuses the search box and asks you to use your keyboard's mic (Gboard / iOS dictation) |
| **Development build** (our own app, `app-frontend`) | Real in-app voice search: text fills in live while you speak |

To test the real mic, install the development build once, then run the dev server as usual.

> Android only for now. An iPhone development build needs a paid Apple Developer account.

---

## 1. One-time setup on your PC

### 1.1 Run the backend so the phone can reach it

The backend must listen on `0.0.0.0`, not `127.0.0.1`. With `127.0.0.1` only your PC can reach it, and the app shows
no data.

```powershell
cd backend
venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 1.2 Point the app at your PC

Find your PC's Wi-Fi IP:

```powershell
ipconfig    # look for "IPv4 Address", e.g. 192.168.1.71
```

Put it in `app-frontend/.env` (this file is yours, do not commit it):

```
EXPO_PUBLIC_API_URL=http://<your-ip>:8001
```

### 1.3 Allow the phone through Windows Firewall

Open **PowerShell as Administrator** (Start → type PowerShell → right-click → *Run as administrator*) and run once:

```powershell
New-NetFirewallRule -DisplayName "Samaj dev (Expo + API)" -Direction Inbound -Protocol TCP -LocalPort 8001,8081 -Action Allow -Profile Any
```

### 1.4 Check from the phone

Phone and PC must be on the **same Wi-Fi**. Open this in the phone's browser:

```
http://<your-ip>:8001/health
```

You should see `{"status":"ok",...}`. If it does not load, see [Troubleshooting](#5-troubleshooting).

---

## 2. Install the development build on your phone (one time)

You do **not** need to build it yourself. Use the build already on Expo:

1. Ask the project owner for the latest **development** build link (Expo → project `app-frontend` → Builds), or open the
   link they share.
2. On the build page, click **Install**. A QR code appears.
3. Scan that QR code with your **Android phone camera**. It downloads an `.apk`.
4. Open the `.apk` and tap **Install**. If Android blocks it, allow *Install unknown apps* for your browser / Files app.
5. A new app called **app-frontend** appears on your phone.

Ignore *Open with Orbit*; that is for installing from a desktop over USB.

---

## 3. Every day: run and connect

```powershell
cd app-frontend
npm install          # first time, or after someone changes package.json
npx expo start       # NO --go flag: this serves the development build
```

On the phone:

1. Open **app-frontend** (not Expo Go).
2. Under *Development servers*, tap the one showing `<your-ip>:8081`, or tap **Scan QR code** inside the app and scan the
   QR in your terminal.

> Do **not** scan the terminal QR with the phone camera or Expo Go. You will get
> *"Expo Go couldn't open exp+app-frontend://..."*. That link only opens in the development build.

Code changes reload live. You do not need to reinstall the app for JS/TS changes.

---

## 4. Test the mic

1. Log in and open the **Directory** tab.
2. Tap the mic icon next to the search box.
3. Allow microphone permission (first time only).
4. Say a member's name. The search box fills in as you speak and results update.
5. Tap the mic again to stop early.

Recognition is set to English (India) even when the app is in Gujarati or Hindi, because the server matches names in
English.

---

## 5. Troubleshooting

| Problem | Fix |
| --- | --- |
| *Expo Go couldn't open exp+app-frontend* | You opened the QR in Expo Go. Open the **app-frontend** app and connect from inside it (step 3). |
| Mic icon only shows the "use your keyboard mic" message | You are in Expo Go, not the development build. |
| *Could not hear you, please try again* | Speak right after tapping. Make sure the **Google** app is installed and up to date; Android speech recognition uses it. |
| App opens but shows no data / network error | Backend is on `127.0.0.1` (use `--host 0.0.0.0`), wrong IP in `.env`, or firewall rule missing. Re-check step 1.4. Restart `npx expo start` after editing `.env`. |
| Phone browser cannot open `http://<your-ip>:8001/health` even with the firewall rule | The router blocks devices from talking to each other (common on office / guest Wi-Fi). Turn on your phone's hotspot, connect the PC to it, and use the PC's new IP in `.env`. |
| `Port 8081 is being used by another process` | An old Expo is still running. Close it (Ctrl+C in its terminal) and start again. |
| `Set-NetConnectionProfile ... PermissionDenied` | PowerShell is not elevated. Use the firewall rule in step 1.3 from an Administrator PowerShell instead. |

### Only want to use Expo Go?

```powershell
npx expo start --go
```

Scan with Expo Go (Android: scanner inside Expo Go; iPhone: Camera app). The mic falls back to keyboard dictation.

---

## 6. When a new development build is needed

Rebuild **only** when native code changes: adding a library with native code (`npx expo install <pkg>`), or changing
`plugins` / permissions in `app-frontend/app.json`. JS/TS changes never need a rebuild.

You need access to the `app-frontend` project on Expo (ask the owner to invite you), then:

```powershell
cd app-frontend
npx eas-cli@latest login
npx eas-cli@latest build --profile development --platform android
```

Takes about 20 minutes. When it says *Succeeded*, share the build page link with the team; everyone reinstalls from
step 2.

Build profiles live in [app-frontend/eas.json](../app-frontend/eas.json).
