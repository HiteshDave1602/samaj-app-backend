import { SymbolView } from 'expo-symbols';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { LANGUAGES, setLang, useLang, useT, type Lang } from '@/lib/i18n';

// Outside the (app) gate, so pending members can switch language too.
export default function Settings() {
  const t = useT();
  const current = useLang();
  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Settings" back />
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 12 }}>
        <Text className="font-headline text-xl text-brand">{t('Language')}</Text>
        <View className="rounded-3xl border border-line bg-white">
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
                  tintColor={Palette.primary.DEFAULT}
                />
              )}
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
