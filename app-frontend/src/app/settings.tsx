import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ScreenHeader } from '@/components/ui/form';
import { LANGUAGES, setLang, useLang, useT, type Lang } from '@/lib/i18n';
import { setThemePref, THEMES, usePalette, useThemePref, type ThemePref } from '@/lib/theme';

const THEME_ICONS: Record<ThemePref, SymbolViewProps['name']> = {
  system: { ios: 'circle.lefthalf.filled', android: 'contrast', web: 'contrast' },
  light: { ios: 'sun.max', android: 'light_mode', web: 'light_mode' },
  dark: { ios: 'moon', android: 'dark_mode', web: 'dark_mode' },
};

// Outside the (app) gate, so pending members can switch language and theme too.
export default function Settings() {
  const palette = usePalette();
  const t = useT();
  const current = useLang();
  const theme = useThemePref();
  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Settings" back />
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 12 }}>
        <Text className="font-headline text-xl text-brand">{t('Language')}</Text>
        <View className="rounded-3xl border border-line bg-card">
          {(Object.keys(LANGUAGES) as Lang[]).map((l, i) => (
            <Pressable
              key={l}
              onPress={() => setLang(l)}
              accessibilityRole="radio"
              accessibilityState={{ selected: l === current }}
              className={`flex-row items-center justify-between px-4 py-4 active:opacity-80 ${i ? 'border-t border-line' : ''}`}>
              <Text className={`text-base ${l === current ? 'font-inter-semibold text-primary' : 'font-inter text-ink'}`}>
                {LANGUAGES[l]}
              </Text>
              {l === current && (
                <SymbolView
                  name={{ ios: 'checkmark', android: 'check', web: 'check' }}
                  size={20}
                  tintColor={palette.primary.DEFAULT}
                />
              )}
            </Pressable>
          ))}
        </View>

        <Text className="mt-4 font-headline text-xl text-brand">{t('Appearance')}</Text>
        <View accessibilityRole="radiogroup" className="rounded-3xl border border-line bg-card">
          {(Object.keys(THEMES) as ThemePref[]).map((p, i) => (
            <Pressable
              key={p}
              onPress={() => setThemePref(p)}
              accessibilityRole="radio"
              accessibilityState={{ selected: p === theme }}
              className={`flex-row items-center gap-3 px-4 py-4 active:opacity-80 ${i ? 'border-t border-line' : ''}`}>
              <SymbolView name={THEME_ICONS[p]} size={22} tintColor={p === theme ? palette.primary.DEFAULT : palette.muted} />
              <Text className={`flex-1 text-base ${p === theme ? 'font-inter-semibold text-primary' : 'font-inter text-ink'}`}>
                {t(THEMES[p])}
              </Text>
              {p === theme && (
                <SymbolView
                  name={{ ios: 'checkmark', android: 'check', web: 'check' }}
                  size={20}
                  tintColor={palette.primary.DEFAULT}
                />
              )}
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
