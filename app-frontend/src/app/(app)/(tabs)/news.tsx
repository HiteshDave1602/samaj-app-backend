import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Notice, ScreenHeader } from '@/components/ui/form';
import { Cover, formatDate, useFeed, ViewAdBar } from '@/lib/feed';
import { useLoc, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';

// ponytail: FULLSCREEN ads render inline like banners; make them interstitials when ad layout (FR-51) lands
export default function NewsScreen() {
  const palette = usePalette();
  const t = useT();
  const loc = useLoc();
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
            <SymbolView name={{ ios: 'plus', android: 'add', web: 'add' }} size={16} tintColor={palette['on-primary']} />
            <Text className="font-inter-semibold text-sm text-on-primary">{t('Create news')}</Text>
          </Pressable>
        }
      />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 16 }}>
        {error && <Notice title="Could not load news" body={error} tone={palette.rejected} />}
        {!items && !error && <ActivityIndicator color={palette.primary.DEFAULT} />}
        {items?.length === 0 && <Notice title="No news yet" body="Your city admin hasn't posted anything." tone={palette.info} />}
        {items?.map((n, i) => {
          const ad = n.content_type === 'AD';
          return (
            <Pressable
              key={`${n.content_id}-${i}`} // the feed repeats ads when it rotates them
              onPress={() => router.push({ pathname: '/news/[id]', params: { id: n.content_id } })}
              accessibilityRole="button"
              className="overflow-hidden rounded-3xl border border-line bg-card active:opacity-90">
              <Cover item={n} className="h-36 justify-end p-4">
                {ad && (
                  <Text className="mb-auto self-start rounded-full bg-black/50 px-3 py-1 font-inter-semibold text-xs text-white">
                    {t('Sponsored')}
                  </Text>
                )}
                <Text className="font-headline text-2xl text-white">{loc(n.title, n.title_i18n)}</Text>
              </Cover>
              {(n.body || !ad) && (
                <View className="p-4">
                  {n.body && (
                    <Text numberOfLines={2} className="font-inter text-sm leading-5 text-subtle">
                      {loc(n.body, n.body_i18n)}
                    </Text>
                  )}
                  {!ad && (
                    <View className="mt-3 flex-row items-center justify-between">
                      <Text className="font-inter text-xs text-muted">{formatDate(n.start_at)}</Text>
                      <Text className="font-inter-semibold text-sm text-primary">{t('View')}</Text>
                    </View>
                  )}
                </View>
              )}
              {ad && <ViewAdBar />}
            </Pressable>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}
