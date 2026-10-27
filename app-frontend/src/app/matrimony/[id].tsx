import { router, useLocalSearchParams } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Button, ScreenHeader, StatusView } from '@/components/ui/form';
import { PROFILES } from '@/constants/sample-data';
import { Palette } from '@/constants/theme';

export default function MatrimonyProfile() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const p = PROFILES.find((x) => x.id === id) ?? PROFILES[0];
  const [sent, setSent] = useState(false);
  const first = p.name.split(' ')[0];

  if (sent) {
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <StatusView
          icon={{ ios: 'paperplane.fill', android: 'send', web: 'send' }}
          tone={Palette.secondary}
          title="Biodata request sent"
          body={`${first} will see your request. Nothing is shared until they accept.`}
          action="Back to browsing profiles"
          onAction={() => router.back()}
        />
      </SafeAreaView>
    );
  }

  const details = [
    ['Education', p.education],
    ['Profession', p.profession],
    ['Gotra', p.gotra],
    ['Native', p.native],
    ['City', p.city],
  ];

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Profile" back />
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 20 }}>
        <View className="items-center">
          <Avatar name={p.name} size={112} tone={Palette.secondary} />
          <Text className="mt-3 font-headline text-3xl text-brand">{p.name}</Text>
          <Text className="font-inter text-base text-subtle">
            {p.age} yrs · {p.city}
          </Text>
        </View>

        <View className="rounded-3xl border border-line bg-white p-5">
          {details.map(([label, value], i) => (
            <View key={label} className={`flex-row justify-between py-2.5 ${i ? 'border-t border-line' : ''}`}>
              <Text className="font-inter text-sm text-muted">{label}</Text>
              <Text className="ml-4 flex-1 text-right font-inter-semibold text-sm text-ink">{value}</Text>
            </View>
          ))}
          <Text className="mt-3 font-inter text-sm leading-5 text-subtle">{p.about}</Text>
        </View>

        <View className="flex-row items-center gap-3 rounded-3xl bg-secondary-container p-4">
          <SymbolView name={{ ios: 'lock.fill', android: 'lock', web: 'lock' }} size={22} tintColor={Palette.secondary.DEFAULT} />
          <Text className="flex-1 font-inter text-sm text-secondary">
            <Text className="font-inter-semibold">Full biodata is private.</Text> Visible after {first} accepts your
            request.
          </Text>
        </View>

        {/* ponytail: only flips to the sent state until the biodata-request API exists */}
        <Button title="Send biodata request" onPress={() => setSent(true)} />
      </ScrollView>
    </SafeAreaView>
  );
}
