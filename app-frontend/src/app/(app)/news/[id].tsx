import { Image } from 'expo-image';
import { Redirect, useLocalSearchParams } from 'expo-router';
import { ScrollView, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ScreenHeader } from '@/components/ui/form';
import { mediaUrl } from '@/lib/api';
import { cachedItem, Cover, formatDate } from '@/lib/feed';
import { useLoc } from '@/lib/i18n';

export default function NewsDetail() {
  const loc = useLoc();
  const { id } = useLocalSearchParams<{ id: string }>();
  const n = cachedItem(id);
  // opened without the feed loaded first (deep link, reload): the list is one tap away
  if (!n) return <Redirect href="/news" />;

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="News" back />
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <Cover item={n} className="mx-5 h-52 justify-end rounded-3xl p-5">
          <Text className="font-headline text-3xl text-white">{loc(n.title, n.title_i18n)}</Text>
        </Cover>
        <Text className="px-5 py-4 font-inter text-xs text-muted">{formatDate(n.start_at)}</Text>
        {n.body && <Text className="px-5 font-inter text-base leading-7 text-ink">{loc(n.body, n.body_i18n)}</Text>}
        {n.extra_media_urls.map((u) => (
          <Image
            key={u}
            source={{ uri: mediaUrl(u)! }}
            contentFit="cover"
            style={{ marginHorizontal: 20, marginTop: 16, aspectRatio: 4 / 3, borderRadius: 24 }}
          />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
