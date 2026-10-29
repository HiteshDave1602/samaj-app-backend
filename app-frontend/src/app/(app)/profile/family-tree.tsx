import { Fragment } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { label, loc, useT } from '@/lib/i18n';
import { useHousehold } from '@/lib/family';

// relationships are to the household head, who sits in generation 2
const GENERATION: Record<string, number> = {
  GRANDFATHER: 0, GRANDMOTHER: 0,
  FATHER: 1, MOTHER: 1,
  SPOUSE: 2, BROTHER: 2, SISTER: 2, OTHER: 2,
  SON: 3, DAUGHTER: 3, SON_IN_LAW: 3, DAUGHTER_IN_LAW: 3,
  GRANDSON: 4, GRANDDAUGHTER: 4,
};

// ponytail: groups by generation only; a real tree with branches needs parent links from the API
export default function FamilyTree() {
  const t = useT();
  const { household, error } = useHousehold();
  const people = household
    ? [
        ...household.members.map((m) => ({
          id: m.member_id,
          name: loc(m.full_name, m.full_name_i18n) ?? t('Member'),
          role: t(m.is_household_head ? 'Head' : 'Member'),
          gen: 2,
          head: m.is_household_head,
        })),
        ...household.relatives
          .filter((r) => r.status === 'APPROVED')
          .map((r) => ({ id: r.family_member_id, name: loc(r.full_name, r.full_name_i18n)!, role: label(r.relationship), gen: GENERATION[r.relationship] ?? 2, head: false })),
      ]
    : [];
  const rows = [0, 1, 2, 3, 4].map((g) => people.filter((p) => p.gen === g)).filter((r) => r.length);

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title={household ? t('{name} family', { name: loc(household.family_name, household.family_name_i18n)! }) : 'Family tree'} back />
      <ScrollView contentContainerStyle={{ padding: 20, alignItems: 'center' }}>
        {error && <Notice title="Could not load your family" body={error} tone={Palette.rejected} />}
        {!household && !error && <ActivityIndicator color={Palette.primary.DEFAULT} />}
        {rows.map((row, i) => (
          <Fragment key={i}>
            {i > 0 && <View className="h-8 w-0.5 bg-line" />}
            <View className="flex-row flex-wrap justify-center gap-4">
              {row.map((p) => (
                <View
                  key={p.id}
                  className={`w-28 items-center rounded-3xl border bg-white p-3 ${p.head ? 'border-primary' : 'border-line'}`}>
                  <Avatar name={p.name} size={52} tone={p.head ? Palette.primary : Palette.brand} />
                  <Text numberOfLines={1} className="mt-2 font-inter-semibold text-sm text-ink">
                    {p.name.split(' ')[0]}
                  </Text>
                  <Text className={`font-inter text-xs ${p.head ? 'text-primary' : 'text-muted'}`}>{p.role}</Text>
                </View>
              ))}
            </View>
          </Fragment>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
