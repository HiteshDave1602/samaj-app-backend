import { Image } from 'expo-image';
import { SymbolView } from 'expo-symbols';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Text, View } from 'react-native';
import Animated, { interpolateColor, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';

import { Palettes } from '@/constants/theme';
import { api, mediaUrl } from '@/lib/api';
import { locale, useT } from '@/lib/i18n';

// backend member/feed/api.py FeedItemOut
export type FeedItem = {
  content_id: string;
  content_type: 'NEWS' | 'AD';
  title: string;
  title_i18n: Record<string, string>;
  body: string | null;
  body_i18n: Record<string, string>;
  media_url: string | null;
  creative_format: 'BANNER' | 'FULLSCREEN' | null;
  media_width: number | null;
  media_height: number | null;
  extra_media_urls: string[];
  start_at: string;
};

// The backend has no member GET-by-id, so the detail screen reads the last fetched feed.
let last: FeedItem[] = [];
export const cachedItem = (id: string) => last.find((x) => x.content_id === id);

export function useFeed() {
  const [items, setItems] = useState<FeedItem[]>();
  const [error, setError] = useState<string>();
  // refetch whenever the screen comes back into view: tabs stay mounted, so a mount-only fetch never sees new approvals
  useFocusEffect(
    useCallback(() => {
      api<FeedItem[]>('/member/feed').then(
        (r) => (setItems((last = r)), setError(undefined)),
        (e) => setError(e.message),
      );
    }, []),
  );
  return { items, error };
}

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString(locale(), { day: 'numeric', month: 'short', year: 'numeric' });

// brand fills under white text: the same in both themes
const TINTS = [Palettes.light.secondary, Palettes.light.brand, Palettes.light.primary];

/** News header: the item's photo darkened for legible text, or a brand colour picked from its id. */
export function Cover({ item, className, children }: { item: FeedItem; className: string; children: ReactNode }) {
  const uri = mediaUrl(item.media_url);
  const tint = TINTS[item.content_id.charCodeAt(0) % TINTS.length].DEFAULT;
  return (
    <View className={`overflow-hidden ${className}`} style={{ backgroundColor: tint }}>
      {uri && (
        <>
          <Image source={{ uri }} contentFit="cover" style={{ position: 'absolute', inset: 0 }} />
          <View style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.35)' }} />
        </>
      )}
      {children}
    </View>
  );
}

export const AD_BAR_HEIGHT = 44;
// plain array, built on the JS thread: the animated style runs on the UI thread and can't call .map
const AD_COLORS = TINTS.map((c) => c.DEFAULT);

/** The call-to-action strip under an ad, its fill slowly cycling through the brand colours. */
export function ViewAdBar() {
  const t = useT();
  const p = useSharedValue(0);
  useEffect(() => {
    p.value = withRepeat(withTiming(1, { duration: 2400 }), -1, true);
  }, [p]);
  const fill = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(p.value, [0, 0.5, 1], AD_COLORS),
  }));
  return (
    <Animated.View
      style={[{ height: AD_BAR_HEIGHT, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, fill]}>
      <Text className="font-inter-semibold text-sm text-white">{t('View ad')}</Text>
      <SymbolView name={{ ios: 'chevron.right', android: 'chevron_right', web: 'chevron_right' }} size={16} tintColor="white" />
    </Animated.View>
  );
}
