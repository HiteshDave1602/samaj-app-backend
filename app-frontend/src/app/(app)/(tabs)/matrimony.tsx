import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api } from '@/lib/api';
import { label, useT } from '@/lib/i18n';
import { Cover, education, summary, title, useReceivedRequests, type BiodataRequest, type ProfileCard } from '@/lib/matrimony';

const MY_STATUS: Record<string, string> = {
  DRAFT: 'Draft: add a photo and submit it for review.',
  PENDING_MODERATION: 'Under review by your city admin.',
  APPROVED: 'Live: other members can find you.',
  REJECTED: 'Not approved: open it to fix and resubmit.',
  ARCHIVED: 'Archived.',
};

// ponytail: first 20 profiles, no filters; add search params and next_after paging when there are more
export default function MatrimonyScreen() {
  const t = useT();
  const [profiles, setProfiles] = useState<ProfileCard[]>();
  const [mine, setMine] = useState<{ status: string } | null>(); // null: no profile yet
  const [exchanges, setExchanges] = useState<BiodataRequest[]>([]);
  const [error, setError] = useState<string>();
  const { requests, reload } = useReceivedRequests();

  useEffect(() => {
    api<{ items: ProfileCard[] }>('/member/matrimony/profiles').then((r) => setProfiles(r.items), (e) => setError(e.message));
  }, []);

  // my profile and my requests change on other screens, so refetch on focus
  const loadMine = useCallback(() => {
    api<{ status: string }>('/member/matrimony/profile').then(setMine, () => setMine(null));
    const box = (q: string) =>
      api<{ items: BiodataRequest[] }>(`/member/matrimony/biodata-requests?${q}`).then((r) => r.items, () => []);
    Promise.all([box('box=sent'), box('box=received&status=ACCEPTED')]).then(([sent, accepted]) => setExchanges([...sent, ...accepted]));
  }, []);
  useFocusEffect(loadMine);

  const respond = (id: string, action: 'accept' | 'decline') =>
    api(`/member/matrimony/biodata-requests/${id}/${action}`, { method: 'POST' }).then(
      () => (reload(), loadMine()),
      (e) => setError(e.message),
    );

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Matrimony" />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 24 }}>
        <View className="rounded-3xl bg-secondary p-5">
          <Text className="font-headline text-2xl text-white">{t(mine ? 'Your profile' : 'Find your match')}</Text>
          <Text className="mt-1 font-inter text-sm text-white/80">
            {t(mine ? MY_STATUS[mine.status] : 'Create a matrimonial profile. Your city admin verifies it before others can see it.')}
          </Text>
          <View className="mt-4 self-start">
            <Pressable
              onPress={() => router.push('/matrimony/create')}
              accessibilityRole="button"
              className="rounded-full bg-white px-5 py-2.5 active:opacity-80">
              <Text className="font-inter-semibold text-sm text-secondary">
                {t(mine ? 'Manage my profile' : 'Create matrimonial profile')}
              </Text>
            </Pressable>
          </View>
        </View>

        {exchanges.length > 0 && (
          <View className="gap-3">
            <Text className="font-headline text-xl text-brand">{t('Your requests')}</Text>
            {exchanges.map((r) => (
              <Pressable
                key={r.request_id}
                onPress={() => router.push({ pathname: '/matrimony/[id]', params: { id: r.counterpart_profile_id } })}
                accessibilityRole="button"
                className="flex-row items-center gap-3 rounded-3xl border border-line bg-white p-4 active:opacity-80">
                {r.counterpart && <Cover p={r.counterpart} size={44} />}
                <View className="flex-1">
                  <Text className="font-inter-semibold text-base text-ink">
                    {r.counterpart ? title(r.counterpart) : t('Profile no longer listed')}
                  </Text>
                  <Text className="font-inter text-sm text-subtle">
                    {t(r.sent_by_me ? 'You asked' : 'They asked')} · {label(r.status)}
                  </Text>
                </View>
                {r.status === 'ACCEPTED' && <Text className="font-inter-semibold text-sm text-primary">{t('View biodata')}</Text>}
              </Pressable>
            ))}
          </View>
        )}

        {error && <Notice title="Something went wrong" body={error} tone={Palette.rejected} />}

        {requests.length > 0 && (
          <View className="gap-3">
            <Text className="font-headline text-xl text-brand">{t('Biodata requests')}</Text>
            {requests.map((r) => (
              <View key={r.request_id} className="rounded-3xl border border-line bg-white p-4">
                <View className="flex-row items-center gap-3">
                  {r.counterpart && <Cover p={r.counterpart} size={44} />}
                  <Text className="flex-1 font-inter text-sm text-subtle">
                    {t('{who} wants to view your biodata.', {
                      who: r.counterpart ? `${title(r.counterpart)} (${summary(r.counterpart)})` : t('A member'),
                    })}
                  </Text>
                </View>
                <View className="mt-3 flex-row gap-2">
                  <View className="flex-1">
                    <Button title="Accept" small onPress={() => respond(r.request_id, 'accept')} />
                  </View>
                  <View className="flex-1">
                    <Button title="Decline" small variant="outlined" onPress={() => respond(r.request_id, 'decline')} />
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}

        <View className="gap-3">
          <Text className="font-headline text-xl text-brand">{t('Verified profiles')}</Text>
          {!profiles && !error && <ActivityIndicator color={Palette.secondary.DEFAULT} />}
          {profiles?.length === 0 && <Notice title="No profiles yet" body="Approved profiles will show up here." tone={Palette.info} />}
          {profiles?.map((p) => (
            <Pressable
              key={p.profile_id}
              onPress={() => router.push({ pathname: '/matrimony/[id]', params: { id: p.profile_id } })}
              accessibilityRole="button"
              className="flex-row items-center gap-4 rounded-3xl border border-line bg-white p-4 active:opacity-80">
              <Cover p={p} size={64} />
              <View className="flex-1">
                <View className="flex-row items-center gap-2">
                  <Text className="font-inter-semibold text-base text-ink">{title(p)}</Text>
                  <Text className="rounded-full bg-approved-container px-2 py-0.5 font-inter-semibold text-[10px] text-approved">
                    {t('Verified')}
                  </Text>
                </View>
                <Text className="mt-0.5 font-inter text-sm text-subtle">{summary(p)}</Text>
                <Text numberOfLines={1} className="font-inter text-sm text-subtle">
                  {p.occupation ?? education(p)}
                </Text>
              </View>
              <Text className="font-inter-semibold text-sm text-primary">{t('View')}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
