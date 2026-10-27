import { Fragment } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, ScreenHeader } from '@/components/ui/form';
import { FAMILY, ME } from '@/constants/sample-data';
import { Palette } from '@/constants/theme';

const GENERATION: Record<string, number> = {
  Grandfather: 0, Grandmother: 0,
  Father: 1, Mother: 1,
  Self: 2, Spouse: 2, Brother: 2, Sister: 2,
  Son: 3, Daughter: 3,
};

// ponytail: groups by generation only; a real tree with branches needs parent links from the API
export default function FamilyTree() {
  const people = [
    { id: 'me', name: ME.name, relation: 'Self' },
    ...FAMILY.filter((f) => f.status === 'APPROVED'),
  ];
  const rows = [0, 1, 2, 3]
    .map((g) => people.filter((p) => GENERATION[p.relation] === g))
    .filter((r) => r.length);

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Family tree" back />
      <ScrollView contentContainerStyle={{ padding: 20, alignItems: 'center' }}>
        {rows.map((row, i) => (
          <Fragment key={i}>
            {i > 0 && <View className="h-8 w-0.5 bg-line" />}
            <View className="flex-row flex-wrap justify-center gap-4">
              {row.map((p) => {
                const me = p.id === 'me';
                return (
                  <View
                    key={p.id}
                    className={`w-28 items-center rounded-3xl border bg-white p-3 ${me ? 'border-primary' : 'border-line'}`}>
                    <Avatar name={p.name} size={52} tone={me ? Palette.primary : Palette.brand} />
                    <Text numberOfLines={1} className="mt-2 font-inter-semibold text-sm text-ink">
                      {p.name.split(' ')[0]}
                    </Text>
                    <Text className={`font-inter text-xs ${me ? 'text-primary' : 'text-muted'}`}>
                      {me ? 'You' : p.relation}
                    </Text>
                  </View>
                );
              })}
            </View>
          </Fragment>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
