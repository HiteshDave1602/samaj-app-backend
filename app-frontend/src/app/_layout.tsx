import '@/global.css';

import { BalooBhai2_700Bold } from '@expo-google-fonts/baloo-bhai-2';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  useFonts,
} from '@expo-google-fonts/inter';
import { DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useState } from 'react';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { loadLang } from '@/lib/i18n';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    BalooBhai2_700Bold,
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
  });
  const [langLoaded, setLangLoaded] = useState(false);
  useEffect(() => {
    loadLang().finally(() => setLangLoaded(true));
  }, []);
  // native splash stays up until fonts and the saved language are ready; the overlay hides it on mount
  if (!fontsLoaded || !langLoaded) return null;

  return (
    <ThemeProvider value={DefaultTheme}>
      <Stack screenOptions={{ headerShown: false }} />
      <AnimatedSplashOverlay />
    </ThemeProvider>
  );
}
