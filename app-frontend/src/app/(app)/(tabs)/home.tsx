import { Image } from 'expo-image';
import { router, useFocusEffect, type Href } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar } from '@/components/ui/form';
import { api } from '@/lib/api';
import { Cover, formatDate, useFeed, ViewAdBar } from '@/lib/feed';
import { locale, tWords, useLoc, useT } from '@/lib/i18n';
import { Cover as ProfileCover, title, useReceivedRequests } from '@/lib/matrimony';
import { usePalette } from '@/lib/theme';

type Icon = SymbolViewProps['name'];

// backend member/panchang/api.py PanchangOut
type Panchang = { panchang_date: string; tithi: string; nakshatra: string; yoga: string };
// backend member/directory/schema.py BirthdayEntry (the fields used here)
type Birthday = {
  id: string;
  full_name: string | null;
  full_name_i18n: Record<string, string>;
  household_id: string | null;
  photo_url: string | null;
  birthday: string; // upcoming birthday, YYYY-MM-DD
  days_away: number;
};

const MODULES: { title: string; sub: string; tag: string; icon: Icon; color: 'primary' | 'secondary' | 'brand' | 'accent'; href: Href }[] = [
  {
    title: 'Member Directory',
    sub: 'Search families & bloodline',
    tag: 'Members',
    icon: { ios: 'person.3.fill', android: 'groups', web: 'groups' },
    color: 'primary',
    href: '/directory',
  },
  {
    title: 'Matrimony',
    sub: 'Admin-verified profiles',
    tag: 'Verified',
    icon: { ios: 'heart.fill', android: 'favorite', web: 'favorite' },
    color: 'secondary',
    href: '/matrimony',
  },
  {
    title: 'News & Gallery',
    sub: 'Photos, sammelan updates',
    tag: 'New',
    icon: { ios: 'newspaper.fill', android: 'newspaper', web: 'newspaper' },
    color: 'brand',
    href: '/news',
  },
  {
    title: 'Panchang',
    sub: 'Tithi, nakshatra & yoga',
    tag: 'Daily',
    icon: { ios: 'sun.max.fill', android: 'wb_sunny', web: 'wb_sunny' },
    color: 'accent',
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

export default function HomeScreen() {
  const palette = usePalette();
  const t = useT();
  const loc = useLoc();
  const { width } = useWindowDimensions();
  const cardWidth = width - 40;
  const [slide, setSlide] = useState(0);
  const items = useFeed().items;
  // every live news item and ad, in feed order; the feed repeats ads when it rotates them, so keep each once
  const news = useMemo(
    () => (items ?? []).filter((n, i, all) => all.findIndex((x) => x.content_id === n.content_id) === i),
    [items],
  );
  // Endless loop: a copy of the first banner sits after the last. Sliding onto the copy looks like "next",
  // then the list jumps, without animation, to the identical real first banner: it never rewinds through the others.
  const banners = useMemo(() => (news.length > 1 ? [...news, news[0]] : news), [news]);
  const slider = useRef<FlatList>(null);
  const currentSlide = useRef(0);
  const dragging = useRef(false);
  const step = cardWidth + 12;

  useEffect(() => {
    const count = news.length;
    const show = (i: number, animated: boolean) => {
      slider.current?.scrollToOffset({ offset: i * step, animated });
      currentSlide.current = i;
      setSlide(i % Math.max(count, 1));
    };
    show(0, false); // the banner set changed: start over
    if (count < 2) return;

    let jump: ReturnType<typeof setTimeout>;
    const id = setInterval(() => {
      if (dragging.current) return; // never pull the list away from a finger
      const next = currentSlide.current + 1;
      show(next, true);
      // on the copy: swap to the real first once the slide animation (~300 ms) is over
      if (next >= count) jump = setTimeout(() => show(0, false), 600);
    }, 3000);
    return () => (clearInterval(id), clearTimeout(jump));
  }, [news.length, step]);
  const { requests } = useReceivedRequests();
  const [birthdays, setBirthdays] = useState<Birthday[]>([]);
  // on focus, not once: a failed fetch (server restarting, network blip) would otherwise hide the row until app restart
  useFocusEffect(
    useCallback(() => {
      // optional section: hide on error. The row scrolls sideways through them all (~150/week now).
      // ponytail: 200 is the server's cap; past that, page it or add a "See all" screen
      api<Birthday[]>('/member/directory/birthdays?limit=200').then(setBirthdays, () => {});
    }, []),
  );
  const [panchang, setPanchang] = useState<Panchang | string>(); // string: why it isn't available
  useEffect(() => {
    api<Panchang>('/member/panchang').then(setPanchang, (e) => setPanchang(e.message));
  }, []);
  // the page carries the unread count; one item is the smallest page. Refetch on focus: the screen clears it
  const [unread, setUnread] = useState(0);
  useFocusEffect(
    useCallback(() => {
      api<{ unread: number }>('/member/notifications?limit=1').then((r) => setUnread(r.unread), () => {});
    }, []),
  );

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <View className="flex-row items-center gap-3 px-5 py-3">
        <Image source={require('@/assets/images/logo.png')} style={{ width: 40, height: 40 }} />
        <View className="flex-1">
          <Text className="font-inter text-xs text-muted">{t('Jay Shree Krishna')}</Text>
          <Text className="font-headline text-lg text-brand">{t('Pragati Samaj')}</Text>
        </View>
        <Pressable
          onPress={() => router.push('/notifications')}
          accessibilityRole="button"
          accessibilityLabel={unread ? t('Notifications, {n} unread', { n: unread }) : t('Notifications')}
          className="p-2">
          <SymbolView
            name={{ ios: 'bell', android: 'notifications', web: 'notifications' }}
            size={24}
            tintColor={palette.ink}
          />
          {unread > 0 && (
            <View className="absolute right-1 top-1 h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1">
              <Text className="font-inter-semibold text-[10px] text-on-accent">{unread > 9 ? '9+' : unread}</Text>
            </View>
          )}
        </Pressable>
        <Pressable
          onPress={() => router.push('/settings')}
          accessibilityRole="button"
          accessibilityLabel={t('Settings')}
          className="-ml-2 p-2">
          <SymbolView
            name={{ ios: 'gearshape', android: 'settings', web: 'settings' }}
            size={24}
            tintColor={palette.ink}
          />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <FlatList
          ref={slider}
          data={banners}
          horizontal
          // snapToInterval alone: pagingEnabled pages by the screen width, which is wider than a card step
          snapToInterval={step}
          snapToAlignment="start"
          decelerationRate="fast"
          disableIntervalMomentum
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ paddingHorizontal: 20, gap: 12 }}
          keyExtractor={(n, i) => (i === news.length ? 'loop' : n.content_id)}
          getItemLayout={(_, i) => ({ length: step, offset: 20 + i * step, index: i })}
          onScrollBeginDrag={() => (dragging.current = true)}
          onMomentumScrollEnd={(e) => {
            dragging.current = false;
            let i = Math.round(e.nativeEvent.contentOffset.x / step);
            if (i >= news.length && news.length > 1) {
              i = 0; // swiped onto the copy: same swap as the timer
              slider.current?.scrollToOffset({ offset: 0, animated: false });
            }
            currentSlide.current = i;
            setSlide(i);
          }}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push({ pathname: '/news/[id]', params: { id: item.content_id } })}
              accessibilityRole="button"
              style={{ width: cardWidth }}
              className="overflow-hidden rounded-3xl active:opacity-90">
              {/* an ad's cover gives up the bar's height so every banner is h-44 */}
              <Cover
                item={item}
                className={`justify-end p-5 ${item.content_type === 'AD' ? 'h-[132px]' : 'h-44'}`}>
                <Text className="mb-auto self-start rounded-full bg-accent px-3 py-1 font-inter-semibold text-xs text-on-accent">
                  {t(item.content_type === 'AD' ? 'Sponsored' : 'Latest news')}
                </Text>
                <Text numberOfLines={item.content_type === 'AD' ? 1 : 2} className="font-headline text-2xl text-white">
                  {loc(item.title, item.title_i18n)}
                </Text>
                {item.content_type === 'NEWS' && <Text className="font-inter text-sm text-white/80">{formatDate(item.start_at)}</Text>}
              </Cover>
              {item.content_type === 'AD' && <ViewAdBar />}
            </Pressable>
          )}
        />
        <View className="mt-3 flex-row flex-wrap justify-center gap-2 px-5">
          {news.map((n, i) => (
            <View
              key={n.content_id}
              className={`h-2 rounded-full ${i === Math.min(slide, Math.max(news.length - 1, 0)) ? 'w-6 bg-primary' : 'w-2 bg-line'}`}
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

        {birthdays.length > 0 && (
          <View className="mt-6">
            <SectionTitle title="Upcoming birthdays" />
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ paddingHorizontal: 20, gap: 16 }}>
              {birthdays.map((b) => {
                const name = loc(b.full_name, b.full_name_i18n) ?? t('Member');
                const [y, mo, d] = b.birthday.split('-').map(Number); // local date: new Date('YYYY-MM-DD') is UTC
                const date = new Date(y, mo - 1, d).toLocaleDateString(locale(), { day: 'numeric', month: 'short' });
                const when =
                  b.days_away === 0 ? t('Today') : b.days_away === 1 ? t('Tomorrow') : t('In {n} days', { n: b.days_away });
                return (
                  <Pressable
                    key={b.id}
                    onPress={() => router.push({ pathname: '/directory/[id]', params: { id: b.household_id! } })}
                    disabled={!b.household_id}
                    accessibilityRole="button"
                    accessibilityLabel={t("{name}'s birthday, {when}", { name, when: `${when}, ${date}` })}
                    className="w-20 items-center">
                    <Avatar name={name} size={64} tone={b.days_away === 0 ? palette.accent : palette.primary} photo={b.photo_url} />
                    <Text numberOfLines={1} className="mt-1 font-inter-medium text-xs text-ink">{name}</Text>
                    {/* today: "Today" says it all; later days: the date, which tells more than "In 5 days" */}
                    <Text className={`font-inter text-[11px] ${b.days_away === 0 ? 'text-accent' : 'text-subtle'}`}>
                      {b.days_away === 0 ? when : date}
                    </Text>
                  </Pressable>
                );
              })}
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
                className="rounded-3xl border border-line bg-card p-4 active:opacity-80">
                <View className="flex-row items-start justify-between">
                  <View
                    className="h-11 w-11 items-center justify-center rounded-2xl"
                    style={{ backgroundColor: palette[m.color].container }}>
                    <SymbolView name={m.icon} size={22} tintColor={palette[m.color].DEFAULT} />
                  </View>
                  <Text
                    className="rounded-full px-2 py-0.5 font-inter-semibold text-[10px]"
                    style={{ backgroundColor: palette[m.color].container, color: palette[m.color].DEFAULT }}>
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
