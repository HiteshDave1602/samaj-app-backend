import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api } from '@/lib/api';
import { label, loc, useT } from '@/lib/i18n';

// backend member/directory/schema.py HouseholdView
type Person = {
  kind: 'MEMBER' | 'RELATIVE';
  id: string;
  full_name: string | null;
  full_name_i18n: Record<string, string>;
  relationship: string | null;
  is_household_head: boolean;
  phone: string | null;
  phone_hidden: boolean;
  address: string | null;
  photo_url: string | null;
};
type I18n = Record<string, string>;
type Household = {
  family_name: string;
  family_name_i18n: I18n;
  native_place: string | null;
  native_place_i18n: I18n;
  city_name: string;
  city_name_i18n: I18n;
  people: Person[];
};

export default function HouseholdScreen() {
  const t = useT();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [h, setH] = useState<Household>();
  const [error, setError] = useState<string>();
  useEffect(() => {
    api<Household>(`/member/directory/households/${id}`).then(setH, (e) => setError(e.message));
  }, [id]);

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title={h ? t('{name} family', { name: loc(h.family_name, h.family_name_i18n)! }) : 'Family'} back />
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 12 }}>
        {error && <Notice title="Could not load this family" body={error} tone={Palette.rejected} />}
        {!h && !error && <ActivityIndicator color={Palette.primary.DEFAULT} />}
        {h && (
          <Text className="font-inter text-sm text-subtle">
            {[loc(h.city_name, h.city_name_i18n), h.native_place && t('Native: {place}', { place: loc(h.native_place, h.native_place_i18n)! })].filter(Boolean).join(' · ')}
          </Text>
        )}
        {h?.people.map(({ full_name, full_name_i18n, ...p }) => ({ ...p, full_name: loc(full_name, full_name_i18n) })).map((p) => (
          <View key={p.id} className="rounded-3xl border border-line bg-white p-4">
            <View className="flex-row items-center gap-3">
              <Avatar name={p.full_name ?? '?'} size={48} tone={p.is_household_head ? Palette.primary : Palette.brand} photo={p.photo_url} />
              <View className="flex-1">
                <Text className="font-inter-semibold text-base text-ink">{p.full_name ?? t('Member')}</Text>
                <Text className="font-inter text-sm text-subtle">
                  {p.is_household_head ? t('Head of family') : p.relationship ? label(p.relationship) : t('Member')}
                </Text>
              </View>
              {p.phone && (
                <Pressable
                  onPress={() => Linking.openURL(`tel:${p.phone}`)}
                  accessibilityRole="button"
                  accessibilityLabel={t('Call {name}', { name: p.full_name ?? '' })}
                  className="h-10 justify-center rounded-full bg-surface px-4 active:opacity-80">
                  <Text className="font-inter-medium text-sm text-primary">{t('Call')}</Text>
                </Pressable>
              )}
              {p.phone_hidden && <Text className="font-inter text-xs text-muted">{t('Phone hidden')}</Text>}
            </View>
            {p.address && <Text className="mt-2 font-inter text-sm text-subtle">{p.address}</Text>}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
