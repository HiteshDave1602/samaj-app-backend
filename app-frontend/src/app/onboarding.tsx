import { router } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useRef, useState } from 'react';
import { FlatList, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Palette } from '@/constants/theme';

type Slide = {
  icon: SymbolViewProps['name'];
  color: { DEFAULT: string; container: string };
  title: string;
  body: string;
};

const SLIDES: Slide[] = [
  {
    icon: { ios: 'person.3.fill', android: 'groups', web: 'groups' },
    color: Palette.primary,
    title: 'Every family, one directory',
    body: 'Find samaj members by name, city or gotra, and see how families connect.',
  },
  {
    icon: { ios: 'heart.fill', android: 'favorite', web: 'favorite' },
    color: Palette.secondary,
    title: 'Matrimony you can trust',
    body: 'Every profile is verified by your samaj admin. A biodata stays private until its owner accepts your request.',
  },
  {
    icon: { ios: 'newspaper.fill', android: 'newspaper', web: 'newspaper' },
    color: Palette.brand,
    title: 'News, photos and booklets',
    body: 'Sammelan updates, gallery photos, the vasti patrak and by-laws, all in one place.',
  },
  {
    icon: { ios: 'sun.max.fill', android: 'wb_sunny', web: 'wb_sunny' },
    color: Palette.accent,
    title: 'Daily Panchang',
    body: 'Tithi, nakshatra, Rahu Kaal and Choghadiya for today, every morning.',
  },
];

// ponytail: goes to /home until the login screen exists, then point this at /login
const finish = () => router.replace('/home');

export default function Onboarding() {
  const { width } = useWindowDimensions();
  const list = useRef<FlatList<Slide>>(null);
  const [index, setIndex] = useState(0);
  const isLast = index === SLIDES.length - 1;

  const next = () => {
    if (isLast) return finish();
    list.current?.scrollToOffset({ offset: (index + 1) * width });
    setIndex(index + 1);
  };

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <FlatList
        ref={list}
        data={SLIDES}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        keyExtractor={(s) => s.title}
        onMomentumScrollEnd={(e) => setIndex(Math.round(e.nativeEvent.contentOffset.x / width))}
        renderItem={({ item }) => (
          <View style={{ width }} className="flex-1 items-center justify-center px-8">
            <View
              className="h-64 w-64 items-center justify-center rounded-full"
              style={{ backgroundColor: item.color.container }}>
              <View
                className="h-40 w-40 items-center justify-center rounded-full"
                style={{ backgroundColor: item.color.DEFAULT }}>
                <SymbolView name={item.icon} size={64} tintColor="#FFFFFF" />
              </View>
            </View>
            <Text className="mt-12 text-center font-headline text-3xl text-brand">{item.title}</Text>
            <Text className="mt-3 text-center font-inter text-base leading-6 text-subtle">
              {item.body}
            </Text>
          </View>
        )}
      />

      <View className="flex-row justify-center gap-2 py-6">
        {SLIDES.map((s, i) => (
          <View
            key={s.title}
            className={`h-2 rounded-full ${i === index ? 'w-6 bg-primary' : 'w-2 bg-line'}`}
          />
        ))}
      </View>

      <View className="gap-2 px-6 pb-4">
        <Pressable
          onPress={next}
          accessibilityRole="button"
          className="items-center rounded-full bg-primary py-4 active:opacity-80">
          <Text className="font-inter-semibold text-base text-white">
            {isLast ? 'Get started' : 'Next'}
          </Text>
        </Pressable>
        <Pressable
          onPress={finish}
          accessibilityRole="button"
          className={`items-center py-3 ${isLast ? 'opacity-0' : ''}`}
          disabled={isLast}>
          <Text className="font-inter-medium text-base text-primary">Skip</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
