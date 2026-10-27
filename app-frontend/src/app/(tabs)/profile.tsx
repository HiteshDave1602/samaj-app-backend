import { router } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Button, ScreenHeader } from '@/components/ui/form';
import { FAMILY, ME } from '@/constants/sample-data';
import { Palette } from '@/constants/theme';

const DETAILS = [
  ['Age', `${ME.age} yrs`],
  ['Gender', ME.gender],
  ['Profession', ME.profession],
  ['Gotra', ME.gotra],
  ['City', ME.city],
];

export default function ProfileScreen() {
  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Profile" />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 24 }}>
        <View className="items-center rounded-3xl border border-line bg-white p-5">
          <Avatar name={ME.name} size={88} />
          <Text className="mt-3 font-headline text-2xl text-brand">{ME.name}</Text>
          <View className="mt-4 w-full flex-row flex-wrap gap-y-3">
            {DETAILS.map(([label, value]) => (
              <View key={label} className="w-1/2">
                <Text className="font-inter text-xs text-muted">{label}</Text>
                <Text className="font-inter-semibold text-base text-ink">{value}</Text>
              </View>
            ))}
          </View>
        </View>

        <View className="gap-3">
          <Text className="font-headline text-xl text-brand">Family members</Text>
          {FAMILY.map((f) => (
            <View key={f.id} className="flex-row items-center gap-3 rounded-2xl border border-line bg-white p-3">
              <Avatar name={f.name} size={44} tone={Palette.brand} />
              <View className="flex-1">
                <Text className="font-inter-semibold text-base text-ink">{f.name}</Text>
                <Text className="font-inter text-sm text-subtle">{f.relation}</Text>
              </View>
              {f.status === 'PENDING' && (
                <Text className="rounded-full bg-pending-container px-2.5 py-1 font-inter-semibold text-[11px] text-pending">
                  Pending review
                </Text>
              )}
            </View>
          ))}
        </View>

        <View className="flex-row gap-3">
          <View className="flex-1">
            <Button title="Add member" onPress={() => router.push('/profile/add-member')} />
          </View>
          <View className="flex-1">
            <Button title="View family tree" variant="outlined" onPress={() => router.push('/profile/family-tree')} />
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
