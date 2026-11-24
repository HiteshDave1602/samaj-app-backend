import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Notice, StatusView } from '@/components/ui/form';
import { api, logout, restoreSession } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';

type Status = 'PENDING' | 'ACTIVE' | 'REJECTED' | 'ARCHIVED';
// city_id null: registered for a city not set up yet, so the Super Admin (not a City Admin) reviews it
type Me = { status: Status; rejection_reason: string | null; city_id: string | null };

// Two ways in:
// - with `status` param, no session: just registered (register.tsx) or login refused (login.tsx) because the
//   membership isn't approved yet. Only approved members get a session, so the way on is logging in again later.
// - logged in: an approved member whose name/DOB edit sent the profile back to review; "Check again" refreshes.
export default function Pending() {
  const palette = usePalette();
  const t = useT();
  const params = useLocalSearchParams<{ status?: Status; reason?: string; newCity?: string }>();
  const outside = !!params.status;
  const [me, setMe] = useState<Me>();
  const [error, setError] = useState<string>();

  const check = useCallback(async () => {
    const s = await restoreSession();
    if (!s) return router.replace('/login');
    if (s.member_status === 'ACTIVE') return router.replace('/home');
    api<Me>('/member/me').then(
      (m) => (setMe(m), setError(undefined)),
      (e) => setError(e.message),
    );
  }, []);

  useEffect(() => {
    if (!outside) check();
  }, [check, outside]);

  const rejected = (outside ? params.status : me?.status) === 'REJECTED';
  const reason = outside ? params.reason : me?.rejection_reason;
  const newCity = outside ? !!params.newCity : !!me && !me.city_id;
  return (
    <SafeAreaView className="flex-1 bg-cream">
      <StatusView
        icon={
          rejected
            ? { ios: 'xmark.circle.fill', android: 'cancel', web: 'cancel' }
            : { ios: 'person.badge.clock.fill', android: 'pending', web: 'pending' }
        }
        tone={rejected ? palette.rejected : palette.pending}
        title={rejected ? 'Membership not approved' : 'Awaiting approval'}
        body={
          rejected
            ? reason || t('Please contact your city admin.')
            : t(newCity
              ? 'Your city is not set up yet. The Super Admin will add it and verify your details. You can use the app once your membership is approved.'
              : 'Your city admin will verify your details. You can use the app once they approve your membership.')
            + (outside ? ' ' + t('Log in with your mobile number after approval.') : '')
        }
        action={outside ? 'Go to login' : 'Check again'}
        onAction={outside ? () => router.replace('/login') : check}
      />
      {!outside && (
        <View className="gap-3 px-6 pb-6">
          {error && <Notice title="Could not check your status" body={error} tone={palette.rejected} />}
          <Button title="Edit details / upload ID" variant="outlined" onPress={() => router.push('/edit-profile')} />
          <Button title="Log out" variant="tonal" onPress={() => logout().then(() => router.replace('/login'))} />
        </View>
      )}
    </SafeAreaView>
  );
}
