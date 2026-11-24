import { router, useFocusEffect } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useCallback, useState, type ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Button, Notice, Problem, ScreenHeader } from '@/components/ui/form';
import { api, logout } from '@/lib/api';
import { label, loc, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';

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
  gotra: string | null;
  education: string | null;
  marital_status: string | null;
  occupation: string | null;
  hobby: string | null;
  blood_group: string | null;
};

function age(dob: string) {
  const [y, m, d] = dob.split('-').map(Number);
  const now = new Date();
  return now.getFullYear() - y - (now.getMonth() + 1 < m || (now.getMonth() + 1 === m && now.getDate() < d) ? 1 : 0);
}

const ICON = 42; // row icon circle

/** A titled card of list rows, settings-style. */
function Section({ title, children }: { title: string; children: ReactNode }) {
  const t = useT();
  return (
    <View>
      <Text
        className="font-inter-semibold text-xs uppercase tracking-wider text-muted"
        style={{ marginBottom: 10, marginLeft: 6 }}>
        {t(title)}
      </Text>
      <View className="overflow-hidden rounded-3xl border border-line bg-card" style={{ paddingVertical: 6 }}>
        {children}
      </View>
    </View>
  );
}

function Row({
  icon,
  label,
  hint,
  danger,
  expanded,
  first,
  onPress,
}: {
  icon: SymbolViewProps['name'];
  label: string;
  hint?: string;
  danger?: boolean;
  first?: boolean; // no divider above the first row of a card
  expanded?: boolean;
  onPress: () => void;
}) {
  const palette = usePalette();
  const t = useT();
  const tone = danger ? palette.rejected : palette.primary;
  return (
    <>
      {/* divider starts after the icon, like a native settings list */}
      {!first && <View className="bg-line" style={{ height: 1, marginLeft: 16 + ICON + 14 }} />}
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityState={expanded === undefined ? undefined : { expanded }}
        className="active:opacity-70">
        {/* layout on a plain View: NativeWind's Pressable ignores a style function and dropped the row padding */}
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: 14,
            minHeight: 68,
            paddingHorizontal: 16,
            paddingVertical: 12,
          }}>
          <View
            className="items-center justify-center rounded-full"
            style={{
              width: ICON,
              height: ICON,
              backgroundColor: tone.container,
            }}>
            <SymbolView name={icon} size={20} tintColor={tone.DEFAULT} />
          </View>
          <View className="flex-1" style={{ gap: 2 }}>
            <Text
              className={`font-inter-semibold text-base ${danger ? '' : 'text-ink'}`}
              style={danger ? { color: tone.DEFAULT } : undefined}>
              {t(label)}
            </Text>
            {hint && <Text className="font-inter text-xs text-muted">{t(hint)}</Text>}
          </View>
          <SymbolView
            name={
              expanded === undefined
                ? {
                    ios: 'chevron.right',
                    android: 'chevron_right',
                    web: 'chevron_right',
                  }
                : {
                    ios: expanded ? 'chevron.up' : 'chevron.down',
                    android: expanded ? 'expand_less' : 'expand_more',
                    web: expanded ? 'expand_less' : 'expand_more',
                  }
            }
            size={18}
            tintColor={palette.muted}
          />
        </View>
      </Pressable>
    </>
  );
}

export default function ProfileScreen() {
  const palette = usePalette();
  const t = useT();
  const [me, setMe] = useState<Me>();
  const [error, setError] = useState<string>();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown>();

  async function deleteAccount() {
    setDeleting(true);
    setDeleteError(undefined);
    try {
      await api('/member/me', { method: 'DELETE' });
      await logout(); // the server already ended every session; this clears the tokens on this phone
      router.replace('/login');
    } catch (e) {
      setDeleteError(e);
      setDeleting(false);
    }
  }
  // refetch on focus so edits made on /edit-profile show on return
  useFocusEffect(
    useCallback(() => {
      api<Me>('/member/me').then(setMe, (e) => setError(e.message));
    }, []),
  );

  const name = me && (loc(me.full_name, me.full_name_i18n) ?? t('Member'));
  const details = me
    ? [
        ['Age', me.dob ? t('{n} yrs', { n: age(me.dob) }) : '—'],
        ['Gender', me.gender ? label(me.gender) : '—'],
        ['Family', loc(me.family_name, me.family_name_i18n) ?? '—'],
        ['Native place', loc(me.native_place, me.native_place_i18n) ?? '—'],
        ['City', loc(me.city_name, me.city_name_i18n)!],
        ['Mobile', me.mobile ?? '—'],
        ['Gotra / Vatan', me.gotra ?? '—'],
        ['Marital status', me.marital_status ? t(me.marital_status) : '—'],
        ['Education', me.education ?? '—'],
        ['Occupation', me.occupation ?? '—'],
        ['Blood group', me.blood_group ?? '—'],
        ['Hobby', me.hobby ?? '—'],
      ]
    : [];

  return (
    <SafeAreaView edges={['top']} className="flex-1 bg-cream">
      <ScreenHeader title="Profile" />
      <ScrollView
        contentContainerStyle={{
          paddingHorizontal: 20,
          paddingBottom: 48,
          gap: 28,
        }}>
        {error && <Notice title="Could not load your profile" body={error} tone={palette.rejected} />}
        <View className="items-center rounded-3xl border border-line bg-card p-5">
          {me ? (
            <>
              <Avatar name={name!} size={88} photo={me.photo_url} />
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
            !error && <ActivityIndicator color={palette.primary.DEFAULT} />
          )}
        </View>

        <Section title="Family">
          <Row
            first
            icon={{
              ios: 'person.badge.plus',
              android: 'person_add',
              web: 'person_add',
            }}
            label="Add family member"
            hint="Your city admin approves it"
            onPress={() => router.push('/profile/add-member')}
          />
          <Row
            icon={{
              ios: 'person.3.fill',
              android: 'family_restroom',
              web: 'family_restroom',
            }}
            label="View family tree"
            onPress={() => router.push('/profile/family-tree')}
          />
        </Section>

        <Section title="Account">
          <Row
            first
            icon={{
              ios: 'rectangle.portrait.and.arrow.right',
              android: 'logout',
              web: 'logout',
            }}
            label="Log out"
            onPress={() => logout().then(() => router.replace('/login'))}
          />
          <Row
            icon={{ ios: 'trash', android: 'delete', web: 'delete' }}
            label="Delete my account"
            danger
            expanded={confirming}
            onPress={() => (setDeleteError(undefined), setConfirming(!confirming))}
          />
          {/* two steps in place rather than a native dialog, which the web build doesn't have */}
          {confirming && (
            <View
              style={{
                gap: 12,
                paddingHorizontal: 16,
                paddingTop: 4,
                paddingBottom: 10,
              }}>
              <View className="gap-1 rounded-2xl p-4" style={{ backgroundColor: palette.rejected.container }}>
                <Text className="font-inter-semibold text-sm" style={{ color: palette.rejected.DEFAULT }}>
                  {t('Delete account?')}
                </Text>
                <Text className="font-inter text-sm leading-5" style={{ color: palette.rejected.DEFAULT }}>
                  {t(
                    'You will leave the directory and matrimony, and be logged out on every device. You can register again later with the same number; your city admin will review it like a new registration.',
                  )}
                </Text>
              </View>
              <Problem title="Could not delete your account" error={deleteError} />
              <View className="flex-row gap-3">
                <View className="flex-1">
                  <Button title="Cancel" variant="outlined" small disabled={deleting} onPress={() => setConfirming(false)} />
                </View>
                <Pressable
                  onPress={deleteAccount}
                  disabled={deleting}
                  accessibilityRole="button"
                  className={`flex-1 items-center rounded-full px-4 py-2 ${deleting ? 'opacity-40' : 'active:opacity-80'}`}
                  style={{ backgroundColor: palette.rejected.DEFAULT }}>
                  <Text className="font-inter-semibold text-sm" style={{ color: palette.rejected.container }}>
                    {t(deleting ? 'Deleting…' : 'Delete')}
                  </Text>
                </Pressable>
              </View>
            </View>
          )}
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}
