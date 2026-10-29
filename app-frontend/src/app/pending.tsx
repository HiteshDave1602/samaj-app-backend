import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Notice, StatusView } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, logout, restoreSession } from '@/lib/api';
import { useT } from '@/lib/i18n';

type Me = { status: 'PENDING' | 'ACTIVE' | 'REJECTED' | 'ARCHIVED'; rejection_reason: string | null };

// Members land here until a City Admin approves them; "Check again" refreshes the session to pick up the new status.
export default function Pending() {
  useT();
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
    check();
  }, [check]);

  const rejected = me?.status === 'REJECTED';
  return (
    <SafeAreaView className="flex-1 bg-cream">
      <StatusView
        icon={
          rejected
            ? { ios: 'xmark.circle.fill', android: 'cancel', web: 'cancel' }
            : { ios: 'person.badge.clock.fill', android: 'pending', web: 'pending' }
        }
        tone={rejected ? Palette.rejected : Palette.pending}
        title={rejected ? 'Membership not approved' : 'Awaiting approval'}
        body={
          rejected
            ? me.rejection_reason ?? 'Please contact your city admin.'
            : 'Your city admin will verify your details. You can use the app once they approve your membership.'
        }
        action="Check again"
        onAction={check}
      />
      <View className="gap-3 px-6 pb-6">
        {error && <Notice title="Could not check your status" body={error} tone={Palette.rejected} />}
        {/* a rejected member's edit resubmits the profile; either status can upload the ID document */}
        <Button
          title={rejected ? 'Fix details & resubmit' : 'Edit details / upload ID'}
          variant="outlined"
          onPress={() => router.push('/edit-profile')}
        />
        <Button title="Log out" variant="tonal" onPress={() => logout().then(() => router.replace('/login'))} />
      </View>
    </SafeAreaView>
  );
}
