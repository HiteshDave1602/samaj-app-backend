import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, initials, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, authedImage } from '@/lib/api';
import { label, loc, useT } from '@/lib/i18n';
import { Cover, education, height, summary, title, useReceivedRequests, type BiodataRequest, type ProfileCard } from '@/lib/matrimony';

const MY_STATUS: Record<string, string> = {
  DRAFT: 'Draft: add a photo and submit it for review.',
  PENDING_MODERATION: 'Under review by your city admin.',
  APPROVED: 'Live: other members can find you.',
  REJECTED: 'Not approved: open it to fix and resubmit.',
  ARCHIVED: 'Archived.',
};

// label -> [age_min, age_max] for GET /profiles
const AGES: Record<string, [number, number?]> = { '18-25': [18, 25], '26-30': [26, 30], '31-35': [31, 35], '36+': [36] };
type City = { city_id: string; name: string; name_i18n: Record<string, string> };

// ponytail: first 20 profiles; add next_after paging when there are more
export default function MatrimonyScreen() {
  const t = useT();
  const [profiles, setProfiles] = useState<ProfileCard[]>();
  const [mine, setMine] = useState<{ status: string } | null>(); // null: no profile yet
  const [exchanges, setExchanges] = useState<BiodataRequest[]>([]);
  const [error, setError] = useState<string>();
  const { requests, reload } = useReceivedRequests();
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState<string>();
  const [ageBand, setAgeBand] = useState<string>();
  const [bookmarks, setBookmarks] = useState(new Set<string>());

  useEffect(() => {
    api<City[]>('/member/auth/cities').then(setCities, () => {});
  }, []);

  const cityId = cities.find((c) => loc(c.name, c.name_i18n) === city)?.city_id;
  useEffect(() => {
    const params = new URLSearchParams();
    const [min, max] = ageBand ? AGES[ageBand] : [];
    if (min) params.set('age_min', String(min));
    if (max) params.set('age_max', String(max));
    if (cityId) params.set('city_id', cityId);
    api<{ items: ProfileCard[] }>(`/member/matrimony/profiles?${params}`).then(
      (r) => (setProfiles(r.items), setError(undefined)),
      (e) => setError(e.message),
    );
  }, [ageBand, cityId]);

  // my profile and my requests change on other screens, so refetch on focus
  const loadMine = useCallback(() => {
    api<{ status: string }>('/member/matrimony/profile').then(setMine, () => setMine(null));
    const box = (q: string) =>
      api<{ items: BiodataRequest[] }>(`/member/matrimony/biodata-requests?${q}`).then((r) => r.items, () => []);
    Promise.all([box('box=sent'), box('box=received&status=ACCEPTED')]).then(([sent, accepted]) => setExchanges([...sent, ...accepted]));
  }, []);
  useFocusEffect(loadMine);

  // latest request either way per profile, so each card knows whether interest was already expressed
  const requestFor = new Map([...requests, ...exchanges].map((r) => [r.counterpart_profile_id, r]));
  const expressInterest = (id: string) =>
    api(`/member/matrimony/profiles/${id}/biodata-request`, { method: 'POST' }).then(loadMine, (e) => setError(e.message));

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
          {/* tapping the selected chip again clears it */}
          <View className="gap-4 rounded-3xl border border-line bg-white p-4">
            <Chips label="Age" options={Object.keys(AGES)} value={ageBand} onChange={(v) => setAgeBand(v === ageBand ? undefined : v)} />
            <Chips label="City" options={cities.map((c) => loc(c.name, c.name_i18n)!)} value={city} onChange={(v) => setCity(v === city ? undefined : v)} />
          </View>
          {!profiles && !error && <ActivityIndicator color={Palette.secondary.DEFAULT} />}
          {profiles?.length === 0 &&
            (ageBand || city ? (
              <Notice title="No matching profiles" body="Try another age or city, or clear the filters." tone={Palette.info} />
            ) : (
              <Notice title="No profiles yet" body="Approved profiles will show up here." tone={Palette.info} />
            ))}
          {/* the server never lists your own profile (FR-27) */}
          {profiles?.map((p) => {
            const req = requestFor.get(p.profile_id);
            const saved = bookmarks.has(p.profile_id);
            const open = () => router.push({ pathname: '/matrimony/[id]', params: { id: p.profile_id } });
            return (
              <Pressable
                key={p.profile_id}
                onPress={open}
                accessibilityRole="button"
                className="overflow-hidden rounded-3xl border border-line bg-white shadow-sm active:opacity-90">
                <View style={{ height: 320 }} className="bg-secondary-container">
                  {p.cover_photo_url ? (
                    <Image source={authedImage(p.cover_photo_url)} style={{ width: '100%', height: '100%' }} contentFit="cover" />
                  ) : (
                    <View className="flex-1 items-center justify-center">
                      <Text className="font-headline text-6xl text-secondary">{initials(title(p))}</Text>
                    </View>
                  )}
                  <View className="absolute left-3 top-3 flex-row items-center gap-1.5 rounded-full bg-white/90 px-3 py-1.5">
                    <SymbolView name={{ ios: 'checkmark.seal.fill', android: 'verified', web: 'verified' }} size={18} tintColor={Palette.secondary.DEFAULT} />
                    <Text className="font-inter-semibold text-xs text-ink">{t('Verified')}</Text>
                  </View>
                  {/* ponytail: shortlist lives in screen state, like directory bookmarks; persist once an API exists */}
                  <Pressable
                    onPress={() => {
                      const next = new Set(bookmarks);
                      if (saved) next.delete(p.profile_id);
                      else next.add(p.profile_id);
                      setBookmarks(next);
                    }}
                    accessibilityRole="button"
                    accessibilityLabel={t(saved ? 'Remove {name} from saved' : 'Save {name}', { name: title(p) })}
                    accessibilityState={{ selected: saved }}
                    className="absolute right-3 top-3 h-11 w-11 items-center justify-center rounded-full bg-white">
                    <SymbolView
                      name={{ ios: saved ? 'heart.fill' : 'heart', android: saved ? 'favorite' : 'favorite_border', web: 'favorite' }}
                      size={22}
                      tintColor={Palette.secondary.DEFAULT}
                    />
                  </Pressable>
                  <View className="absolute inset-x-0 bottom-0 gap-1 bg-black/45 px-4 py-3">
                    <Text className="font-headline text-2xl text-white">
                      {title(p)}
                      {p.age != null && <Text className="font-inter-semibold text-base text-accent">{`  ${t('{n} yrs', { n: p.age })}`}</Text>}
                    </Text>
                    <View className="flex-row flex-wrap items-center gap-x-3 gap-y-1">
                      {p.height_cm != null && (
                        <View className="flex-row items-center gap-1">
                          <SymbolView name={{ ios: 'ruler', android: 'straighten', web: 'straighten' }} size={16} tintColor="#FFFFFF" />
                          <Text className="font-inter text-sm text-white">{height(p.height_cm)}</Text>
                        </View>
                      )}
                      <View className="flex-row items-center gap-1">
                        <SymbolView name={{ ios: 'mappin.and.ellipse', android: 'location_on', web: 'location_on' }} size={16} tintColor="#FFFFFF" />
                        <Text className="font-inter text-sm text-white">{loc(p.location_city_name, p.location_city_name_i18n)}</Text>
                      </View>
                    </View>
                  </View>
                </View>
                <View className="gap-3 p-4">
                  <View className="flex-row flex-wrap rounded-2xl border border-line bg-cream p-3">
                    {(
                      [
                        ['Education', education(p)],
                        ['Profession', p.occupation],
                        ['Gotra / Kula', p.gotra],
                        ['Native origin', loc(p.native_place, p.native_place_i18n)],
                      ] as const
                    ).map(([k, v]) => (
                      <View key={k} className="w-1/2 py-1.5 pr-2">
                        <Text className="font-inter-semibold text-[11px] uppercase tracking-wide text-secondary">{t(k)}</Text>
                        <Text numberOfLines={1} className="font-inter-medium text-sm text-ink">{v || '—'}</Text>
                      </View>
                    ))}
                  </View>
                  {p.about && (
                    <Text numberOfLines={2} className="font-inter text-sm leading-5 text-subtle">
                      {p.about}
                    </Text>
                  )}
                  <View className="flex-row gap-3">
                    <View className="flex-1">
                      <Button
                        title="View Biodata"
                        variant="tonal"
                        onPress={() =>
                          req?.status === 'ACCEPTED' ? router.push({ pathname: '/matrimony/biodata', params: { profile: p.profile_id } }) : open()
                        }
                      />
                    </View>
                    <View className="flex-1">
                      {/* an open or accepted request blocks a second one; declined/withdrawn can be re-sent */}
                      {req && (req.status === 'PENDING' || req.status === 'ACCEPTED') ? (
                        <Button title={req.status === 'PENDING' ? 'Interest sent' : 'Accepted'} disabled />
                      ) : (
                        <Button title="Express Interest" onPress={() => expressInterest(p.profile_id)} />
                      )}
                    </View>
                  </View>
                </View>
              </Pressable>
            );
          })}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
