import { Image } from 'expo-image';
import { router, type Href } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useEffect, useState } from 'react';
import { FlatList, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Palette } from '@/constants/theme';
import { api } from '@/lib/api';
import { Cover, formatDate, useFeed } from '@/lib/feed';
import { tWords, useT } from '@/lib/i18n';
import { Cover as ProfileCover, title, useReceivedRequests } from '@/lib/matrimony';

type Icon = SymbolViewProps['name'];

// backend member/panchang/api.py PanchangOut
type Panchang = { panchang_date: string; tithi: string; nakshatra: string; yoga: string };

const MODULES: { title: string; sub: string; tag: string; icon: Icon; color: typeof Palette.primary; href: Href }[] = [
  {
    title: 'Member Directory',
    sub: 'Search families & bloodline',
    tag: 'Members',
    icon: { ios: 'person.3.fill', android: 'groups', web: 'groups' },
    color: Palette.primary,
    href: '/directory',
  },
  {
    title: 'Matrimony',
    sub: 'Admin-verified profiles',
    tag: 'Verified',
    icon: { ios: 'heart.fill', android: 'favorite', web: 'favorite' },
    color: Palette.secondary,
    href: '/matrimony',
  },
  {
    title: 'News & Gallery',
    sub: 'Photos, sammelan updates',
    tag: 'New',
    icon: { ios: 'newspaper.fill', android: 'newspaper', web: 'newspaper' },
    color: Palette.brand,
    href: '/news',
  },
  {
    title: 'Panchang',
    sub: 'Tithi, nakshatra & yoga',
    tag: 'Daily',
    icon: { ios: 'sun.max.fill', android: 'wb_sunny', web: 'wb_sunny' },
    color: Palette.accent,
    href: '/panchang',
  },
];

function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  const t = useT();
  return (
    <View className="mb-3 flex-row items-center justify-between px-5">
      <Text className="font-headline text-xl text-brand">{t(title)}</Text>
      {action && (
        <Pressable onPress={onAction} accessibilityRole="button">
          <Text className="font-inter-medium text-sm text-primary">{t(action)}</Text>
        </Pressable>
      )}
    </View>
  );
}

// ponytail: the bell doesn't navigate yet; wire it when notifications land
export default function HomeScreen() {
  const t = useT();
  const { width } = useWindowDimensions();
  const cardWidth = width - 40;
  const [slide, setSlide] = useState(0);
  const news = useFeed().items?.filter((n) => n.content_type === 'NEWS').slice(0, 5) ?? [];
  const { requests } = useReceivedRequests();
  const [panchang, setPanchang] = useState<Panchang | string>(); // string: why it isn't available
  useEffect(() => {
    api<Panchang>('/member/panchang').then(setPanchang, (e) => setPanchang(e.message));
  }, []);

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <View className="flex-row items-center gap-3 px-5 py-3">
        <Image source={require('@/assets/images/logo.png')} style={{ width: 40, height: 40 }} />
        <View className="flex-1">
          <Text className="font-inter text-xs text-muted">{t('Jay Shree Krishna')}</Text>
          <Text className="font-headline text-lg text-brand">{t('Pragati Samaj')}</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel={t('Notifications')} className="p-2">
          <SymbolView
            name={{ ios: 'bell', android: 'notifications', web: 'notifications' }}
            size={24}
            tintColor={Palette.ink}
          />
        </Pressable>
        <Pressable
          onPress={() => router.push('/settings')}
          accessibilityRole="button"
          accessibilityLabel={t('Settings')}
          className="-ml-2 p-2">
          <SymbolView
            name={{ ios: 'gearshape', android: 'settings', web: 'settings' }}
            size={24}
            tintColor={Palette.ink}
          />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <FlatList
          data={news}
          horizontal
          pagingEnabled
          snapToInterval={cardWidth + 12}
          decelerationRate="fast"
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ paddingHorizontal: 20, gap: 12 }}
          keyExtractor={(n) => n.content_id}
          onMomentumScrollEnd={(e) =>
            setSlide(Math.round(e.nativeEvent.contentOffset.x / (cardWidth + 12)))
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push({ pathname: '/news/[id]', params: { id: item.content_id } })}
              accessibilityRole="button"
              style={{ width: cardWidth }}
              className="active:opacity-90">
              <Cover item={item} className="h-44 justify-end rounded-3xl p-5">
                <Text className="mb-auto self-start rounded-full bg-accent px-3 py-1 font-inter-semibold text-xs text-ink">
                  {t('Latest news')}
                </Text>
                <Text numberOfLines={2} className="font-headline text-2xl text-white">{item.title}</Text>
                <Text className="font-inter text-sm text-white/80">{formatDate(item.start_at)}</Text>
              </Cover>
            </Pressable>
          )}
        />
        <View className="mt-3 flex-row justify-center gap-2">
          {news.map((n, i) => (
            <View
              key={n.content_id}
              className={`h-2 rounded-full ${i === slide ? 'w-6 bg-primary' : 'w-2 bg-line'}`}
            />
          ))}
        </View>

        {requests.length > 0 && (
          <View className="mt-6">
            <SectionTitle title="Biodata requests" action="See all" onAction={() => router.push('/matrimony')} />
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ paddingHorizontal: 20, gap: 16 }}>
              {requests.map((r) => (
                <Pressable
                  key={r.request_id}
                  onPress={() => router.push('/matrimony')}
                  accessibilityRole="button"
                  className="w-16 items-center">
                  {r.counterpart && <ProfileCover p={r.counterpart} size={64} />}
                  <Text numberOfLines={1} className="mt-1 font-inter text-xs text-subtle">
                    {r.counterpart?.age ? t('{n} yrs', { n: r.counterpart.age }) : r.counterpart ? title(r.counterpart) : t('Member')}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        )}

        {panchang !== undefined && (
          <View className="mx-5 mt-6 rounded-3xl bg-accent-container p-5">
            <Text className="font-inter-semibold text-xs uppercase tracking-wider text-subtle">
              {t("Today's Panchang")}{typeof panchang === 'object' && ` · ${formatDate(panchang.panchang_date)}`}
            </Text>
            {typeof panchang === 'object' ? (
              <>
                <Text className="mt-2 font-headline text-4xl text-ink">{tWords(t, panchang.tithi)}</Text>
                <Text className="font-inter text-sm text-subtle">
                  {t('{nakshatra} Nakshatra · {yoga} Yoga', { nakshatra: tWords(t, panchang.nakshatra, 'nakshatra'), yoga: tWords(t, panchang.yoga, 'yoga') })}
                </Text>
              </>
            ) : (
              <Text className="mt-2 font-inter text-sm text-subtle">{panchang}</Text>
            )}
          </View>
        )}

        <View className="mt-6">
          <SectionTitle title="Community services" />
          <View className="flex-row flex-wrap gap-3 px-5">
            {MODULES.map((m) => (
              <Pressable
                key={m.title}
                onPress={() => router.push(m.href)}
                accessibilityRole="button"
                style={{ width: (width - 52) / 2 }}
                className="rounded-3xl border border-line bg-white p-4 active:opacity-80">
                <View className="flex-row items-start justify-between">
                  <View
                    className="h-11 w-11 items-center justify-center rounded-2xl"
                    style={{ backgroundColor: m.color.container }}>
                    <SymbolView name={m.icon} size={22} tintColor={m.color.DEFAULT} />
                  </View>
                  <Text
                    className="rounded-full px-2 py-0.5 font-inter-semibold text-[10px]"
                    style={{ backgroundColor: m.color.container, color: m.color.DEFAULT }}>
                    {t(m.tag)}
                  </Text>
                </View>
                <Text className="mt-3 font-inter-semibold text-base text-ink">{t(m.title)}</Text>
                <Text className="mt-0.5 font-inter text-xs text-subtle">{t(m.sub)}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
