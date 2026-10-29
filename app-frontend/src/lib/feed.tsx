import { Image } from 'expo-image';
import { useEffect, useState, type ReactNode } from 'react';
import { View } from 'react-native';

import { Palette } from '@/constants/theme';
import { api, mediaUrl } from '@/lib/api';
import { locale } from '@/lib/i18n';

// backend member/feed/api.py FeedItemOut
export type FeedItem = {
  content_id: string;
  content_type: 'NEWS' | 'AD';
  title: string;
  body: string | null;
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
  useEffect(() => {
    api<FeedItem[]>('/member/feed').then((r) => setItems((last = r)), (e) => setError(e.message));
  }, []);
  return { items, error };
}

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString(locale(), { day: 'numeric', month: 'short', year: 'numeric' });

const TINTS = [Palette.secondary, Palette.brand, Palette.primary];

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
