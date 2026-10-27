import { Image, type ImageSource } from 'expo-image';
import type { Href } from 'expo-router';
import { TabList, TabSlot, TabTrigger, Tabs, type TabTriggerSlotProps } from 'expo-router/ui';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Palette } from '@/constants/theme';

// a tinted PNG, or a system symbol for tabs without a custom icon yet
type TabIcon = { image: ImageSource } | { symbol: SymbolViewProps['name'] };

const TABS: { name: string; href: Href; label: string; icon: TabIcon }[] = [
  { name: 'home', href: '/home', label: 'Home', icon: { image: require('@/assets/images/tabIcons/home.png') } },
  // ponytail: system icon until a custom directory PNG is designed
  { name: 'directory', href: '/directory', label: 'Directory', icon: { symbol: { ios: 'person.2.fill', android: 'groups', web: 'groups' } } },
  { name: 'matrimony', href: '/matrimony', label: 'Matrimony', icon: { image: require('@/assets/images/tabIcons/matrimony.png') } },
  { name: 'news', href: '/news', label: 'News', icon: { image: require('@/assets/images/tabIcons/news.png') } },
  { name: 'panchang', href: '/panchang', label: 'Panchang', icon: { image: require('@/assets/images/tabIcons/panchang.png') } },
  { name: 'profile', href: '/profile', label: 'Profile', icon: { image: require('@/assets/images/tabIcons/profile.png') } },
];

// One JS tab bar for every platform: native tabs can't draw the raised active bubble.
export default function AppTabs() {
  const { bottom } = useSafeAreaInsets();

  return (
    <Tabs>
      <TabSlot style={{ flex: 1 }} />
      <TabList asChild>
        <View
          style={{ marginBottom: bottom + 12, elevation: 8 }}
          className="mx-3 h-[68px] flex-row rounded-[28px] border border-line bg-white px-1 shadow-lg shadow-ink/10">
          {TABS.map((t) => (
            <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
              <TabButton label={t.label} icon={t.icon} />
            </TabTrigger>
          ))}
        </View>
      </TabList>
    </Tabs>
  );
}

function Icon({ icon, color, size }: { icon: TabIcon; color: string; size: number }) {
  return 'image' in icon ? (
    <Image source={icon.image} tintColor={color} style={{ width: size, height: size }} />
  ) : (
    <SymbolView name={icon.symbol} tintColor={color} size={size} />
  );
}

// expo-router types `ref` as Ref<View>, which RN 0.88's Pressable rejects; TabTrigger never uses it, so drop it
function TabButton({
  label,
  icon,
  isFocused,
  ref: _ref,
  ...props
}: TabTriggerSlotProps & { label: string; icon: TabIcon }) {
  return (
    <Pressable
      {...props}
      accessibilityRole="tab"
      accessibilityLabel={label}
      accessibilityState={{ selected: isFocused }}
      // TabTrigger's own style lays children out in a row on web; pin width here and stack inside
      style={{ flex: 1, alignItems: 'stretch', justifyContent: 'center' }}>
      <View style={{ flexDirection: 'column', alignItems: 'center' }}>
        {isFocused ? (
          // cream ring around the bubble fakes the notch cut into the bar
          <View className="-mt-8 h-14 w-14 items-center justify-center rounded-full border-4 border-cream bg-primary shadow-md shadow-primary/30">
            <Icon icon={icon} color="#FFFFFF" size={24} />
          </View>
        ) : (
          <Icon icon={icon} color={Palette.muted} size={22} />
        )}
        <Text
          numberOfLines={1}
          className={`mt-1 text-[10px] ${isFocused ? 'font-inter-semibold text-primary' : 'font-inter-medium text-muted'}`}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}
