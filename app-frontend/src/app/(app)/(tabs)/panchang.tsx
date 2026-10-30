import { SymbolView } from 'expo-symbols';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api } from '@/lib/api';
import { locale, useT } from '@/lib/i18n';

// backend member/panchang/api.py PanchangOut
type Panchang = { panchang_date: string; tithi: string; nakshatra: string; yoga: string };

// local calendar date as YYYY-MM-DD (toISOString would shift it to UTC)
const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export default function PanchangScreen() {
  const t = useT();
  const [day, setDay] = useState(() => new Date());
  const [result, setResult] = useState<{ date: string; p?: Panchang; error?: string }>();
  const date = ymd(day);

  useEffect(() => {
    api<Panchang>(`/member/panchang?date=${date}`).then(
      (p) => setResult({ date, p }),
      (e) => setResult({ date, error: e.message }),
    );
  }, [date]);

  const shift = (n: number) => setDay(new Date(day.getFullYear(), day.getMonth(), day.getDate() + n));
  const arrow = (n: number, ios: string, md: string, a11y: string) => (
    <Pressable onPress={() => shift(n)} accessibilityRole="button" accessibilityLabel={t(a11y)} hitSlop={8} className="p-2">
      <SymbolView name={{ ios: ios as never, android: md as never, web: md as never }} size={22} tintColor={Palette.ink} />
    </Pressable>
  );
  const loading = result?.date !== date;

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Panchang" />
      <View className="gap-4 px-5">
        <View className="flex-row items-center justify-between rounded-full border border-line bg-white px-2">
          {arrow(-1, 'chevron.left', 'chevron_left', 'Previous day')}
          <Pressable onPress={() => setDay(new Date())} accessibilityRole="button" accessibilityLabel={t('Go to today')}>
            <Text className="font-inter-semibold text-base text-ink">
              {day.toLocaleDateString(locale(), { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })}
            </Text>
          </Pressable>
          {arrow(1, 'chevron.right', 'chevron_right', 'Next day')}
        </View>

        {loading ? (
          <ActivityIndicator color={Palette.accent.DEFAULT} />
        ) : result.p ? (
          <View className="rounded-3xl bg-accent-container p-5">
            <Text className="font-inter-semibold text-xs uppercase tracking-wider text-subtle">{t('Tithi')}</Text>
            <Text className="mt-1 font-headline text-4xl text-ink">{result.p.tithi}</Text>
            <View className="mt-4 flex-row">
              <View className="w-1/2">
                <Text className="font-inter text-xs text-muted">{t('Nakshatra')}</Text>
                <Text className="font-inter-semibold text-base text-ink">{result.p.nakshatra}</Text>
              </View>
              <View className="w-1/2">
                <Text className="font-inter text-xs text-muted">{t('Yoga')}</Text>
                <Text className="font-inter-semibold text-base text-ink">{result.p.yoga}</Text>
              </View>
            </View>
          </View>
        ) : (
          // ponytail: one message for every failure while Panchang data isn't loaded yet; show result.error once it is
          <Notice title="Coming soon" body="Daily Panchang will be available here soon." tone={Palette.info} />
        )}
      </View>
    </SafeAreaView>
  );
}
