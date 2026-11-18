import { router, useFocusEffect, type Href } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Notice, ScreenHeader } from '@/components/ui/form';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/feed';
import { useLoc, useT } from '@/lib/i18n';
import { Cover, title, type ProfileCard } from '@/lib/matrimony';
import { usePalette } from '@/lib/theme';

// backend member/notification/api.py NotificationOut; payload keys per kind are set in the backend curd calls
type Note = {
  notification_id: string;
  kind: string;
  payload: Record<string, any>;
  created_at: string;
  unread: boolean;
  counterpart: ProfileCard | null;
};

const ICON: Record<'ok' | 'no' | 'heart' | 'news', SymbolViewProps['name']> = {
  ok: { ios: 'checkmark.circle.fill', android: 'check_circle', web: 'check_circle' },
  no: { ios: 'xmark.circle.fill', android: 'cancel', web: 'cancel' },
  heart: { ios: 'heart.fill', android: 'favorite', web: 'favorite' },
  news: { ios: 'newspaper.fill', android: 'newspaper', web: 'newspaper' },
};

// [title, body, where a tap goes], in the current language
function describe(n: Note, t: ReturnType<typeof useT>, loc: ReturnType<typeof useLoc>): [string, string, Href?] {
  const { approved, accepted, reason, name, profile_id, content_id } = n.payload;
  const why = reason ? t('Reason: {reason}', { reason }) : '';
  const who = n.counterpart ? title(n.counterpart) : t('A member');
  switch (n.kind) {
    case 'ACCOUNT_DECISION':
      return approved
        ? [t('Membership approved'), t('Welcome! The directory and matrimony are now open to you.')]
        : [t('Membership not approved'), why];
    case 'FAMILY_DECISION':
      return [t(approved ? 'Family member added' : 'Family member not added'), [name, why].filter(Boolean).join(' · '), '/profile/family-tree'];
    case 'PROFILE_DECISION':
      return approved
        ? [t('Matrimony profile approved'), t('Approved: other members can find your profile.'), '/matrimony/create']
        : [t('Matrimony profile not approved'), why, '/matrimony/create'];
    case 'PHOTO_DECISION':
      return approved
        ? [t('Matrimony photo approved'), t('It now shows on your profile.'), '/matrimony/create']
        : [t('Matrimony photo not approved'), why, '/matrimony/create'];
    case 'NEWS_DECISION':
      return approved
        ? [t('Your news is live'), n.payload.title, { pathname: '/news/[id]', params: { id: content_id } }]
        : [t('Your news was not approved'), [n.payload.title, why].filter(Boolean).join(' · ')];
    case 'NEWS_LIVE': // the feed's live news, newest in the bell too
      return [t('Latest news'), loc(n.payload.title, n.payload.title_i18n)!, { pathname: '/news/[id]', params: { id: content_id } }];
    case 'BIODATA_REQUEST':
      return [t('New biodata request'), t('{who} wants to view your biodata.', { who }), '/matrimony'];
    case 'BIODATA_RESPONSE':
      return accepted
        ? [t('Biodata request accepted'), t('{who} accepted your request. You can now view their biodata.', { who }),
            { pathname: '/matrimony/biodata', params: { profile: profile_id } }]
        : [t('Biodata request declined'), t('{who} declined your request.', { who }),
            n.counterpart ? { pathname: '/matrimony/[id]', params: { id: profile_id } } : undefined];
    default: // a kind newer than this app build
      return [t('Notifications'), ''];
  }
}

// ponytail: newest 50; add offset paging when inboxes grow past that
export default function NotificationsScreen() {
  const palette = usePalette();
  const t = useT();
  const loc = useLoc();
  const [items, setItems] = useState<Note[]>();
  const [error, setError] = useState<string>();

  // opening the screen reads everything; the list keeps this visit's unread marks so new ones stand out
  useFocusEffect(
    useCallback(() => {
      api<{ unread: number; items: Note[] }>('/member/notifications').then(
        (r) => {
          setItems(r.items);
          setError(undefined);
          if (r.unread) api('/member/notifications/read', { method: 'POST' }).catch(() => {});
        },
        (e) => setError(e.message),
      );
    }, []),
  );

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Notifications" back />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 12 }}>
        {error && <Notice title="Something went wrong" body={error} tone={palette.rejected} />}
        {!items && !error && <ActivityIndicator color={palette.primary.DEFAULT} />}
        {items?.length === 0 && (
          <Notice title="No notifications yet" body="News, admin decisions and biodata requests will show up here." tone={palette.info} />
        )}
        {items?.map((n) => {
          const [head, body, href] = describe(n, t, loc);
          const ok = n.payload.approved ?? n.payload.accepted;
          const [tone, icon] =
            n.kind === 'NEWS_LIVE' ? [palette.brand, ICON.news]
            : n.kind === 'BIODATA_REQUEST' ? [palette.secondary, ICON.heart]
            : ok ? [palette.approved, ICON.ok] : [palette.rejected, ICON.no];
          return (
            <Pressable
              key={n.notification_id}
              onPress={href && (() => router.push(href))}
              disabled={!href}
              accessibilityRole={href ? 'button' : undefined}
              className={`flex-row gap-3 rounded-3xl border p-4 active:opacity-80 ${n.unread ? 'border-primary bg-primary-container' : 'border-line bg-card'}`}>
              {n.counterpart ? (
                <Cover p={n.counterpart} size={44} />
              ) : (
                <View className="h-11 w-11 items-center justify-center rounded-full" style={{ backgroundColor: tone.container }}>
                  <SymbolView name={icon} size={24} tintColor={tone.DEFAULT} />
                </View>
              )}
              <View className="flex-1">
                <Text className="font-inter-semibold text-base text-ink">{head}</Text>
                {!!body && <Text className="mt-0.5 font-inter text-sm text-subtle">{body}</Text>}
                <Text className="mt-1 font-inter text-xs text-muted">{formatDate(n.created_at)}</Text>
              </View>
              {n.unread && <View accessibilityLabel={t('New')} className="mt-1.5 h-2.5 w-2.5 rounded-full bg-primary" />}
            </Pressable>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}
