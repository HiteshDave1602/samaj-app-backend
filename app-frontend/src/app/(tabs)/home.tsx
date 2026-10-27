import { Image } from 'expo-image';
import { router, type Href } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useState } from 'react';
import { FlatList, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { initials } from '@/components/ui/form';
import { BIODATA_REQUESTS, NEWS, PROFILES } from '@/constants/sample-data';
import { Palette } from '@/constants/theme';

type Icon = SymbolViewProps['name'];

const REQUESTS = PROFILES.filter((p) => BIODATA_REQUESTS.includes(p.id)).map((p) => p.name);

// ponytail: static sample data until the panchang API is wired in
const PANCHANG = {
  samvat: 'Vikram Samvat 2081',
  month: 'Phalguna',
  tithi: 'Dashami',
  detail: 'Shukla Paksha · Rohini Nakshatra · Shobhana Yoga',
  times: [
    ['Sunrise', '06:42 AM'],
    ['Sunset', '06:18 PM'],
    ['Rahu Kaal', '15:20 – 16:45'],
    ['Abhijit', '12:08 – 12:56'],
  ],
  choghadiya: 'Amrit · until 11:15 AM',
};

const MODULES: { title: string; sub: string; tag: string; icon: Icon; color: typeof Palette.primary; href?: Href }[] = [
  {
    title: 'Member Directory',
    sub: 'Search families & bloodline',
    tag: '1.4k active',
    icon: { ios: 'person.3.fill', android: 'groups', web: 'groups' },
    color: Palette.primary,
    href: '/directory',
  },
  {
    title: 'Matrimony',
    sub: '54 newly verified matches',
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
    title: 'PDF Docs',
    sub: 'Vasti patrak, by-laws',
    tag: 'Booklets',
    icon: { ios: 'doc.text.fill', android: 'description', web: 'description' },
    color: Palette.accent,
  },
];

function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <View className="mb-3 flex-row items-center justify-between px-5">
      <Text className="font-headline text-xl text-brand">{title}</Text>
      {action && (
        <Pressable onPress={onAction} accessibilityRole="button">
          <Text className="font-inter-medium text-sm text-primary">{action}</Text>
        </Pressable>
      )}
    </View>
  );
}

// ponytail: bell, PDF docs and full calendar don't navigate yet; wire them as those screens land
export default function HomeScreen() {
  const { width } = useWindowDimensions();
  const cardWidth = width - 40;
  const [slide, setSlide] = useState(0);

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <View className="flex-row items-center gap-3 px-5 py-3">
        <Image source={require('@/assets/images/logo.png')} style={{ width: 40, height: 40 }} />
        <View className="flex-1">
          <Text className="font-inter text-xs text-muted">Jay Shree Krishna</Text>
          <Text className="font-headline text-lg text-brand">Pragati Samaj</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Notifications" className="p-2">
          <SymbolView
            name={{ ios: 'bell', android: 'notifications', web: 'notifications' }}
            size={24}
            tintColor={Palette.ink}
          />
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <FlatList
          data={NEWS}
          horizontal
          pagingEnabled
          snapToInterval={cardWidth + 12}
          decelerationRate="fast"
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ paddingHorizontal: 20, gap: 12 }}
          keyExtractor={(n) => n.id}
          onMomentumScrollEnd={(e) =>
            setSlide(Math.round(e.nativeEvent.contentOffset.x / (cardWidth + 12)))
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push({ pathname: '/news/[id]', params: { id: item.id } })}
              accessibilityRole="button"
              style={{ width: cardWidth, backgroundColor: item.color.DEFAULT }}
              className="h-44 justify-end rounded-3xl p-5 active:opacity-90">
              <Text className="mb-auto self-start rounded-full bg-accent px-3 py-1 font-inter-semibold text-xs text-ink">
                Latest news
              </Text>
              <Text className="font-headline text-2xl text-white">{item.title}</Text>
              <Text className="font-inter text-sm text-white/80">{item.by}</Text>
            </Pressable>
          )}
        />
        <View className="mt-3 flex-row justify-center gap-2">
          {NEWS.map((n, i) => (
            <View
              key={n.id}
              className={`h-2 rounded-full ${i === slide ? 'w-6 bg-primary' : 'w-2 bg-line'}`}
            />
          ))}
        </View>

        <View className="mt-6">
          <SectionTitle title="Biodata requests" action="See all" onAction={() => router.push('/matrimony')} />
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingHorizontal: 20, gap: 16 }}>
            {REQUESTS.map((name) => (
              <Pressable
                key={name}
                onPress={() => router.push('/matrimony')}
                accessibilityRole="button"
                className="w-16 items-center">
                <View className="h-16 w-16 items-center justify-center rounded-full border-2 border-secondary bg-secondary-container">
                  <Text className="font-inter-semibold text-lg text-secondary">{initials(name)}</Text>
                </View>
                <Text numberOfLines={1} className="mt-1 font-inter text-xs text-subtle">
                  {name.split(' ')[0]}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>

        <View className="mx-5 mt-6 rounded-3xl bg-accent-container p-5">
          <Text className="font-inter-semibold text-xs uppercase tracking-wider text-subtle">
            Auspicious Panchang · {PANCHANG.samvat}
          </Text>
          <View className="mt-2 flex-row items-end gap-3">
            <Text className="font-headline text-4xl text-ink">{PANCHANG.tithi}</Text>
            <Text className="mb-2 font-inter-medium text-sm text-subtle">{PANCHANG.month}</Text>
          </View>
          <Text className="font-inter text-sm text-subtle">{PANCHANG.detail}</Text>

          <View className="mt-4 flex-row flex-wrap gap-y-3">
            {PANCHANG.times.map(([label, value]) => (
              <View key={label} className="w-1/2">
                <Text className="font-inter text-xs text-muted">{label}</Text>
                <Text className="font-inter-semibold text-base text-ink">{value}</Text>
              </View>
            ))}
          </View>

          <View className="mt-4 flex-row items-center justify-between rounded-2xl bg-white/70 px-4 py-3">
            <View className="flex-1">
              <Text className="font-inter text-xs text-muted">Current Choghadiya</Text>
              <Text className="font-inter-semibold text-sm text-ink">{PANCHANG.choghadiya}</Text>
            </View>
            <Text className="font-inter-semibold text-sm text-primary">Full calendar</Text>
          </View>
        </View>

        <View className="mt-6">
          <SectionTitle title="Community services" />
          <View className="flex-row flex-wrap gap-3 px-5">
            {MODULES.map((m) => (
              <Pressable
                key={m.title}
                onPress={m.href ? () => router.push(m.href!) : undefined}
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
                    {m.tag}
                  </Text>
                </View>
                <Text className="mt-3 font-inter-semibold text-base text-ink">{m.title}</Text>
                <Text className="mt-0.5 font-inter text-xs text-subtle">{m.sub}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
