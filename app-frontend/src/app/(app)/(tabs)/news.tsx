import { Image } from 'expo-image';
import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { mediaUrl } from '@/lib/api';
import { Cover, formatDate, useFeed } from '@/lib/feed';
import { useT } from '@/lib/i18n';

// ponytail: FULLSCREEN ads render inline like banners; make them interstitials when ad layout (FR-51) lands
export default function NewsScreen() {
  const t = useT();
  const { items, error } = useFeed();

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader
        title="News"
        right={
          <Pressable
            onPress={() => router.push('/news/create')}
            accessibilityRole="button"
            className="flex-row items-center gap-1 rounded-full bg-primary px-4 py-2 active:opacity-80">
            <SymbolView name={{ ios: 'plus', android: 'add', web: 'add' }} size={16} tintColor="white" />
            <Text className="font-inter-semibold text-sm text-white">{t('Create news')}</Text>
          </Pressable>
        }
      />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 16 }}>
        {error && <Notice title="Could not load news" body={error} tone={Palette.rejected} />}
        {!items && !error && <ActivityIndicator color={Palette.primary.DEFAULT} />}
        {items?.length === 0 && <Notice title="No news yet" body="Your city admin hasn't posted anything." tone={Palette.info} />}
        {items?.map((n) =>
          n.content_type === 'AD' ? (
            <View key={n.content_id} className="overflow-hidden rounded-3xl border border-line bg-white">
              {n.media_url && (
                <Image
                  source={{ uri: mediaUrl(n.media_url)! }}
                  contentFit="cover"
                  style={{ width: '100%', aspectRatio: (n.media_width ?? 16) / (n.media_height ?? 9) }}
                  accessibilityLabel={n.title}
                />
              )}
              <Text className="px-4 py-2 font-inter text-xs text-muted">{t('Sponsored')} · {n.title}</Text>
            </View>
          ) : (
            <Pressable
              key={n.content_id}
              onPress={() => router.push({ pathname: '/news/[id]', params: { id: n.content_id } })}
              accessibilityRole="button"
              className="overflow-hidden rounded-3xl border border-line bg-white active:opacity-90">
              <Cover item={n} className="h-36 justify-end p-4">
                <Text className="font-headline text-2xl text-white">{n.title}</Text>
              </Cover>
              <View className="p-4">
                {n.body && (
                  <Text numberOfLines={2} className="font-inter text-sm leading-5 text-subtle">
                    {n.body}
                  </Text>
                )}
                <View className="mt-3 flex-row items-center justify-between">
                  <Text className="font-inter text-xs text-muted">{formatDate(n.start_at)}</Text>
                  <Text className="font-inter-semibold text-sm text-primary">{t('View')}</Text>
                </View>
              </View>
            </Pressable>
          ),
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
