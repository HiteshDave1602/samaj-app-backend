import { router } from 'expo-router';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, ScreenHeader } from '@/components/ui/form';
import { NEWS } from '@/constants/sample-data';

export default function NewsScreen() {
  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader
        title="News"
        right={<Button title="Create news" small onPress={() => router.push('/news/create')} />}
      />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 16 }}>
        {NEWS.map((n) => (
          <Pressable
            key={n.id}
            onPress={() => router.push({ pathname: '/news/[id]', params: { id: n.id } })}
            accessibilityRole="button"
            className="overflow-hidden rounded-3xl border border-line bg-white active:opacity-90">
            <View className="h-36 justify-end p-4" style={{ backgroundColor: n.color.DEFAULT }}>
              <Text className="font-headline text-2xl text-white">{n.title}</Text>
            </View>
            <View className="p-4">
              <Text numberOfLines={2} className="font-inter text-sm leading-5 text-subtle">
                {n.body}
              </Text>
              <View className="mt-3 flex-row items-center justify-between">
                <Text className="font-inter text-xs text-muted">
                  {n.by} · {n.date}
                </Text>
                <Text className="font-inter-semibold text-sm text-primary">View</Text>
              </View>
            </View>
          </Pressable>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
