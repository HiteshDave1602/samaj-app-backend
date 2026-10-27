import { useLocalSearchParams } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, ScreenHeader } from '@/components/ui/form';
import { NEWS } from '@/constants/sample-data';

export default function NewsDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const n = NEWS.find((x) => x.id === id) ?? NEWS[0];

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="News" back />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <View className="mx-5 h-52 justify-end rounded-3xl p-5" style={{ backgroundColor: n.color.DEFAULT }}>
          <Text className="font-headline text-3xl text-white">{n.title}</Text>
        </View>
        <View className="flex-row items-center gap-3 px-5 py-4">
          <Avatar name={n.by} size={40} />
          <View>
            <Text className="font-inter-semibold text-sm text-ink">{n.by}</Text>
            <Text className="font-inter text-xs text-muted">{n.date}</Text>
          </View>
        </View>
        <Text className="px-5 font-inter text-base leading-7 text-ink">{n.body}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}
