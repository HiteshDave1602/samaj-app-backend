import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Button, ScreenHeader } from '@/components/ui/form';
import { BIODATA_REQUESTS, PROFILES } from '@/constants/sample-data';
import { Palette } from '@/constants/theme';

export default function MatrimonyScreen() {
  // ponytail: accept/decline only hides the card locally until the biodata-request API exists
  const [pending, setPending] = useState(BIODATA_REQUESTS);
  const requests = PROFILES.filter((p) => pending.includes(p.id));

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Matrimony" />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 24 }}>
        {/* ponytail: always shown; hide once the member already has a profile */}
        <View className="rounded-3xl bg-secondary p-5">
          <Text className="font-headline text-2xl text-white">Find your match</Text>
          <Text className="mt-1 font-inter text-sm text-white/80">
            Create a matrimonial profile. Your city admin verifies it before others can see it.
          </Text>
          <View className="mt-4 self-start">
            <Pressable
              onPress={() => router.push('/matrimony/create')}
              accessibilityRole="button"
              className="rounded-full bg-white px-5 py-2.5 active:opacity-80">
              <Text className="font-inter-semibold text-sm text-secondary">Create matrimonial profile</Text>
            </Pressable>
          </View>
        </View>

        {requests.length > 0 && (
          <View className="gap-3">
            <Text className="font-headline text-xl text-brand">Biodata requests</Text>
            {requests.map((p) => (
              <View key={p.id} className="rounded-3xl border border-line bg-white p-4">
                <View className="flex-row items-center gap-3">
                  <Avatar name={p.name} size={44} tone={Palette.secondary} />
                  <Text className="flex-1 font-inter text-sm text-subtle">
                    <Text className="font-inter-semibold text-ink">{p.name}</Text> ({p.age}, {p.city}) wants to
                    view your biodata.
                  </Text>
                </View>
                <View className="mt-3 flex-row gap-2">
                  <View className="flex-1">
                    <Button title="Accept" small onPress={() => setPending(pending.filter((id) => id !== p.id))} />
                  </View>
                  <View className="flex-1">
                    <Button
                      title="Decline"
                      small
                      variant="outlined"
                      onPress={() => setPending(pending.filter((id) => id !== p.id))}
                    />
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}

        <View className="gap-3">
          <Text className="font-headline text-xl text-brand">Verified profiles</Text>
          {PROFILES.map((p) => (
            <Pressable
              key={p.id}
              onPress={() => router.push({ pathname: '/matrimony/[id]', params: { id: p.id } })}
              accessibilityRole="button"
              className="flex-row items-center gap-4 rounded-3xl border border-line bg-white p-4 active:opacity-80">
              <Avatar name={p.name} size={64} tone={Palette.secondary} />
              <View className="flex-1">
                <View className="flex-row items-center gap-2">
                  <Text className="font-inter-semibold text-base text-ink">{p.name}</Text>
                  <Text className="rounded-full bg-approved-container px-2 py-0.5 font-inter-semibold text-[10px] text-approved">
                    Verified
                  </Text>
                </View>
                <Text className="mt-0.5 font-inter text-sm text-subtle">
                  {p.age} yrs · {p.city}
                </Text>
                <Text className="font-inter text-sm text-subtle">{p.profession}</Text>
              </View>
              <Text className="font-inter-semibold text-sm text-primary">View</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
