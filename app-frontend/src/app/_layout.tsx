import '@/global.css';

import { BalooBhai2_700Bold } from '@expo-google-fonts/baloo-bhai-2';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  useFonts,
} from '@expo-google-fonts/inter';
import * as Sentry from '@sentry/react-native';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import * as SystemUI from 'expo-system-ui';
import { useEffect, useState } from 'react';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { loadLang } from '@/lib/i18n';
import { loadTheme, usePalette, useScheme } from '@/lib/theme';

// JS errors, unhandled rejections and native crashes (dev/EAS builds; Expo Go has no native module) go to Sentry.
// Empty DSN: off. __DEV__ splits development (metro) from production (release builds).
if (process.env.EXPO_PUBLIC_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
    environment: __DEV__ ? 'development' : 'production',
    sendDefaultPii: false,
    initialScope: { tags: { app: 'mobile' } },
  });
}

SplashScreen.preventAutoHideAsync();

export default Sentry.wrap(RootLayout);

function RootLayout() {
  const [fontsLoaded] = useFonts({
    BalooBhai2_700Bold,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
  });
  const [prefsLoaded, setPrefsLoaded] = useState(false);
  useEffect(() => {
    Promise.all([loadLang(), loadTheme()]).finally(() => setPrefsLoaded(true));
  }, []);
  const scheme = useScheme();
  const palette = usePalette();
  // the window behind the screens (keyboard resize, transitions) matches them instead of flashing white
  useEffect(() => {
    SystemUI.setBackgroundColorAsync(palette.cream).catch(() => {});
  }, [palette]);
  // native splash stays up until fonts, the saved language and the saved theme are ready; the overlay hides it on mount
  if (!fontsLoaded || !prefsLoaded) return null;

  const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
  const navTheme = {
    ...base,
    colors: {
      ...base.colors,
      primary: palette.primary.DEFAULT,
      background: palette.cream,
      card: palette.card,
      text: palette.ink,
      border: palette.line,
    },
  };

  return (
    <ThemeProvider value={navTheme}>
      <Stack screenOptions={{ headerShown: false }} />
      {/* auto: dark icons on the light theme, light icons on the dark one */}
      <StatusBar style="auto" />
      <AnimatedSplashOverlay />
    </ThemeProvider>
  );
}
