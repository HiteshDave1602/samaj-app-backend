import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, authedImage } from '@/lib/api';
import { label, loc, useT } from '@/lib/i18n';
import { Cover, education, height, summary, title, type ProfileCard } from '@/lib/matrimony';

// backend member/matrimony/schema.py PublicProfileOut
type Profile = ProfileCard & {
  about: string | null;
  photos: { photo_id: string; file_url: string }[];
  biodata_request: {
    request_id: string;
    status: 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN';
    sent_by_me: boolean;
    resend_allowed_at: string | null;
  } | null;
};

const REQUEST_NOTE = {
  PENDING: 'Request sent. Nothing is shared until they accept.',
  ACCEPTED: 'Request accepted. You can now view the full biodata.',
  DECLINED: 'Your request was declined.',
  WITHDRAWN: 'This biodata exchange was withdrawn.',
};

export default function MatrimonyProfile() {
  const t = useT();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [p, setP] = useState<Profile>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () => api<Profile>(`/member/matrimony/profiles/${id}`).then(setP, (e) => setError(e.message)),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function act(path: string) {
    setBusy(true);
    setError(undefined);
    try {
      await api(path, { method: 'POST' });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!p)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Profile" back />
        <View className="p-5">
          {error ? <Notice title="Could not load profile" body={error} tone={Palette.rejected} /> : <ActivityIndicator />}
        </View>
      </SafeAreaView>
    );

  const details = [
    ['Education', education(p)],
    ['Occupation', p.occupation],
    ['Height', p.height_cm ? height(p.height_cm) : null],
    ['Gotra / Kula', p.gotra],
    ['Native origin', loc(p.native_place, p.native_place_i18n)],
    ['Family', label(p.family_background)],
    ['City', p.location_city_name],
    ['Managed by', label(p.managed_by)],
  ].filter(([, v]) => v);
  const req = p.biodata_request;
  // a declined request can be re-sent once the cool-off passes
  const canRequest = !req || req.status === 'WITHDRAWN' || (req.status === 'DECLINED' && !!req.resend_allowed_at && new Date(req.resend_allowed_at) < new Date());

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Profile" back />
      <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 20 }}>
        <View className="items-center">
          <Cover p={p} size={112} />
          <Text className="mt-3 font-headline text-3xl text-brand">{title(p)}</Text>
          <Text className="font-inter text-base text-subtle">{summary(p)}</Text>
        </View>

        {p.photos.length > 1 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
            {p.photos.map((ph) => (
              <Image key={ph.photo_id} source={authedImage(ph.file_url)} style={{ width: 120, height: 150, borderRadius: 16 }} />
            ))}
          </ScrollView>
        )}

        <View className="rounded-3xl border border-line bg-white p-5">
          {details.map(([k, v], i) => (
            <View key={k} className={`flex-row justify-between py-2.5 ${i ? 'border-t border-line' : ''}`}>
              <Text className="font-inter text-sm text-muted">{t(k!)}</Text>
              <Text className="ml-4 flex-1 text-right font-inter-semibold text-sm text-ink">{v}</Text>
            </View>
          ))}
          {p.about && <Text className="mt-3 font-inter text-sm leading-5 text-subtle">{p.about}</Text>}
        </View>

        <View className="flex-row items-center gap-3 rounded-3xl bg-secondary-container p-4">
          <SymbolView name={{ ios: 'lock.fill', android: 'lock', web: 'lock' }} size={22} tintColor={Palette.secondary.DEFAULT} />
          <Text className="flex-1 font-inter text-sm text-secondary">
            {req ? t(REQUEST_NOTE[req.status]) : (
              <>
                <Text className="font-inter-semibold">{t('Full biodata is private.')}</Text> {t('Visible after they accept your request.')}
              </>
            )}
          </Text>
        </View>

        {error && <Notice title="Something went wrong" body={error} tone={Palette.rejected} />}
        {canRequest && (
          <Button
            title={busy ? 'Sending…' : 'Send biodata request'}
            disabled={busy}
            onPress={() => act(`/member/matrimony/profiles/${id}/biodata-request`)}
          />
        )}
        {req?.status === 'ACCEPTED' && (
          <>
            <Button title="View biodata" onPress={() => router.push({ pathname: '/matrimony/biodata', params: { profile: id } })} />
            <Button
              title="Withdraw exchange"
              variant="outlined"
              disabled={busy}
              onPress={() => act(`/member/matrimony/biodata-requests/${req.request_id}/withdraw`)}
            />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
