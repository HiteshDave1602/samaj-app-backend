# Testing the mic / speech-to-text feature (Expo development build)

Speech-to-text uses `expo-speech-recognition`, a native module. **It does not work in Expo Go.** You need a *development build* of this app, built with a free Expo account and EAS.

The project is already prepared:
- `expo-speech-recognition` and `expo-dev-client` are installed
- `app.json` has the microphone and speech permissions and the `expo-speech-recognition` plugin

## Android (free, easiest)

### 1. Create an Expo account
Sign up for free at https://expo.dev/signup

### 2. Log in from the terminal
Run everything below from inside `app-frontend/`:

```bash
cd app-frontend
npx eas-cli@latest login
```

### 3. Link the project to your account
```bash
npx eas-cli@latest init
```
This adds `extra.eas.projectId` (and `owner`) to `app.json`.

### 4. (Recommended) Set a real package name
In `app.json`, change `android.package` from the placeholder `com.anonymous.appfrontend` to something like `com.vrattiks.samaj`. Do this before your first build, because changing it later means reinstalling the app.

### 5. Create the build config
```bash
npx eas-cli@latest build:configure
```
Pick **All** or **Android**. This creates `eas.json` with a `development` profile (`developmentClient: true`, `distribution: internal`).

### 6. Build the dev client in the cloud
```bash
npx eas-cli@latest build --profile development --platform android
```
- Say **yes** when asked to generate a new Android keystore.
- On the free tier, builds wait in a queue and take about 10–20 minutes.
- When it finishes, you get a QR code or link to an `.apk`.

### 7. Install it on your phone
Open the link on an Android phone, download the APK, and allow "install unknown apps". An emulator works for the UI, but its mic is unreliable, so test speech on a real phone.

### 8. Start the dev server and connect
```bash
npx expo start --dev-client
```
Open the **installed app** (not Expo Go) and scan the QR code. The phone and PC must be on the same Wi-Fi. If they can't connect, use:
```bash
npx expo start --dev-client --tunnel
```

### 9. Test
Tap the mic icon, allow microphone and speech permission, and speak.

**When to rebuild:** only after you add or change a native package, or a plugin or permission in `app.json` (then repeat step 6). JS and TS changes hot-reload with no rebuild.

## iOS

- Building for a **real iPhone** needs a **paid Apple Developer account ($99/year)**. Then run:
  ```bash
  npx eas-cli@latest device:create    # register your iPhone
  npx eas-cli@latest build --profile development --platform ios
  ```
- The **iOS simulator** is free (add `"ios": { "simulator": true }` to the `development` profile in `eas.json`), but it runs only on a Mac, and speech recognition on the simulator is unreliable.

## Local alternative (no EAS)

If you have Android Studio and the Android SDK installed, you can build on your own PC with a phone connected over USB (USB debugging on). This skips the cloud queue:

```bash
npx expo run:android
```

## Common problems

| Problem | Fix |
|---|---|
| "No development build installed" | You opened Expo Go. Open the app you installed from the EAS build instead. |
| Mic icon does nothing / no text | The phone's speech service is missing. Google's speech recognition comes with the **Google app**, so make sure it's installed and up to date. |
| Phone can't reach the dev server | Use the same Wi-Fi, or run `npx expo start --dev-client --tunnel`. |
| Permission was denied earlier | Phone Settings → Apps → this app → Permissions → allow Microphone. |
