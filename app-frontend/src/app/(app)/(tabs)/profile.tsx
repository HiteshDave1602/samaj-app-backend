import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Button, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, logout, mediaUrl } from '@/lib/api';
import { useHousehold } from '@/lib/family';
import { label, loc, useT } from '@/lib/i18n';

// subset of backend member/profile/schema.py MemberOut that this screen shows
type Me = {
  member_id: string;
  full_name: string | null;
  full_name_i18n: Record<string, string>;
  gender: string | null;
  dob: string | null; // YYYY-MM-DD
  mobile: string | null;
  photo_url: string | null;
  city_name: string;
  city_name_i18n: Record<string, string>;
  family_name: string | null;
  family_name_i18n: Record<string, string>;
  native_place: string | null;
  native_place_i18n: Record<string, string>;
};

function age(dob: string) {
  const [y, m, d] = dob.split('-').map(Number);
  const now = new Date();
  return now.getFullYear() - y - (now.getMonth() + 1 < m || (now.getMonth() + 1 === m && now.getDate() < d) ? 1 : 0);
}

export default function ProfileScreen() {
  const t = useT();
  const [me, setMe] = useState<Me>();
  const [error, setError] = useState<string>();
  // refetch on focus so edits made on /edit-profile show on return
  useFocusEffect(
    useCallback(() => {
      api<Me>('/member/me').then(setMe, (e) => setError(e.message));
    }, []),
  );
  const { household, error: familyError } = useHousehold();
  // other app members in the household, then relatives added by request
  const family = household && [
    ...household.members
      .filter((m) => m.member_id !== me?.member_id)
      .map((m) => ({ id: m.member_id, name: loc(m.full_name, m.full_name_i18n) ?? t('Member'), role: t(m.is_household_head ? 'Head of family' : 'Member'), status: 'APPROVED' })),
    ...household.relatives.map((r) => ({ id: r.family_member_id, name: loc(r.full_name, r.full_name_i18n)!, role: label(r.relationship), status: r.status })),
  ];

  const photo = me && mediaUrl(me.photo_url);
  const name = me && (loc(me.full_name, me.full_name_i18n) ?? t('Member'));
  const details = me
    ? [
        ['Age', me.dob ? t('{n} yrs', { n: age(me.dob) }) : '—'],
        ['Gender', me.gender ? label(me.gender) : '—'],
        ['Family', loc(me.family_name, me.family_name_i18n) ?? '—'],
        ['Native place', loc(me.native_place, me.native_place_i18n) ?? '—'],
        ['City', loc(me.city_name, me.city_name_i18n)!],
        ['Mobile', me.mobile ?? '—'],
      ]
    : [];

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Profile" />
      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 24 }}>
        {error && <Notice title="Could not load your profile" body={error} tone={Palette.rejected} />}
        <View className="items-center rounded-3xl border border-line bg-white p-5">
          {me ? (
            <>
              {photo ? (
                <Image source={{ uri: photo }} style={{ width: 88, height: 88, borderRadius: 44 }} />
              ) : (
                <Avatar name={name!} size={88} />
              )}
              <Text className="mt-3 font-headline text-2xl text-brand">{name}</Text>
              <View className="mt-2">
                <Button title="Edit profile" small variant="outlined" onPress={() => router.push('/edit-profile')} />
              </View>
              <View className="mt-4 w-full flex-row flex-wrap gap-y-3">
                {details.map(([k, value]) => (
                  <View key={k} className="w-1/2">
                    <Text className="font-inter text-xs text-muted">{t(k)}</Text>
                    <Text className="font-inter-semibold text-base text-ink">{value}</Text>
                  </View>
                ))}
              </View>
            </>
          ) : (
            !error && <ActivityIndicator color={Palette.primary.DEFAULT} />
          )}
        </View>

        <View className="gap-3">
          <Text className="font-headline text-xl text-brand">{t('Family members')}</Text>
          {familyError && <Notice title="Could not load your family" body={familyError} tone={Palette.rejected} />}
          {!family && !familyError && <ActivityIndicator color={Palette.primary.DEFAULT} />}
          {family?.length === 0 && (
            <Notice title="No family members yet" body="Add your relatives; your city admin approves each one." tone={Palette.info} />
          )}
          {family?.map((f) => (
            <View key={f.id} className="flex-row items-center gap-3 rounded-2xl border border-line bg-white p-3">
              <Avatar name={f.name} size={44} tone={Palette.brand} />
              <View className="flex-1">
                <Text className="font-inter-semibold text-base text-ink">{f.name}</Text>
                <Text className="font-inter text-sm text-subtle">{f.role}</Text>
              </View>
              {f.status === 'PENDING' && (
                <Text className="rounded-full bg-pending-container px-2.5 py-1 font-inter-semibold text-[11px] text-pending">
                  {t('Pending review')}
                </Text>
              )}
              {f.status === 'REJECTED' && (
                <Text className="rounded-full bg-rejected-container px-2.5 py-1 font-inter-semibold text-[11px] text-rejected">
                  {t('Not approved')}
                </Text>
              )}
            </View>
          ))}
        </View>

        <View className="flex-row gap-3">
          <View className="flex-1">
            <Button title="Add member" onPress={() => router.push('/profile/add-member')} />
          </View>
          <View className="flex-1">
            <Button title="View family tree" variant="outlined" onPress={() => router.push('/profile/family-tree')} />
          </View>
        </View>

        <Button title="Log out" variant="tonal" onPress={() => logout().then(() => router.replace('/login'))} />
      </ScrollView>
    </SafeAreaView>
  );
}
