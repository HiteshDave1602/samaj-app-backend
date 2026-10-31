import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Field, Notice } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, saveSession, type Session } from '@/lib/api';
import { syncLang, useT } from '@/lib/i18n';

type VerifyOut = { registered: boolean; session?: Session; registration_ticket?: string };

// SF-01: the number is checked first, so an unknown number gets "register first" instead of a code. Registering opens
// the form straight away with the number filled in; register.tsx asks for the code at submit.
export default function Login() {
  const t = useT();
  const [mobile, setMobile] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false); // false: asking for the number, true: asking for the code
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [unknown, setUnknown] = useState(false); // no account for this number

  async function run(step: () => Promise<void>) {
    setBusy(true);
    setError(undefined);
    setUnknown(false);
    try {
      await step();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const sendCode = () =>
    run(async () => {
      try {
        await api('/member/auth/otp/send', { method: 'POST', body: { mobile, intent: 'login' } });
      } catch (e) {
        if ((e as { status?: number }).status === 404) return setUnknown(true);
        throw e;
      }
      setCode('');
      setSent(true);
    });
  const register = () => router.push({ pathname: '/register', params: { mobile: mobile.trim() } });

  const verify = () =>
    run(async () => {
      const r = await api<VerifyOut>('/member/auth/otp/verify', { method: 'POST', body: { mobile, code } });
      if (r.session) {
        await saveSession(r.session);
        syncLang(); // the language picked on this device wins over the server's copy
        router.replace('/home');
      } else {
        router.replace({ pathname: '/register', params: { ticket: r.registration_ticket! } });
      }
    });

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1, padding: 24, gap: 18 }}>
          <View className="mb-4 mt-12">
            <Text className="font-headline text-3xl text-brand">{t('Welcome')}</Text>
            <Text className="mt-2 font-inter text-base leading-6 text-subtle">{t('Log in with your mobile number.')}</Text>
          </View>

          {sent ? (
            <>
              <Field
                key="code"
                label={t('Code sent to {mobile}', { mobile: mobile.trim() })}
                value={code}
                onChangeText={(v) => setCode(v.replace(/\D/g, ''))}
                placeholder="6-digit code"
                keyboardType="number-pad"
                textContentType="oneTimeCode"
                autoComplete="sms-otp"
                maxLength={6}
                autoFocus
              />
              {error && <Notice title="Could not log in" body={error} tone={Palette.rejected} />}
              <Button title={busy ? 'Please wait…' : 'Verify'} disabled={busy || code.length !== 6} onPress={verify} />
              <View className="flex-row justify-between">
                <Button title="Change number" variant="outlined" small onPress={() => (setSent(false), setError(undefined))} />
                <Button title="Resend code" variant="outlined" small disabled={busy} onPress={sendCode} />
              </View>
            </>
          ) : (
            <>
              <Field
                key="mobile"
                label="Mobile number"
                value={mobile}
                onChangeText={(v) => (setMobile(v), setUnknown(false))}
                placeholder="98765 43210"
                keyboardType="phone-pad"
                textContentType="telephoneNumber"
                autoComplete="tel"
                hint="Indian numbers need no +91"
                autoFocus
              />
              {error && <Notice title="Could not send the code" body={error} tone={Palette.rejected} />}
              {unknown ? (
                <>
                  <Notice title="No account found" body="This number is not registered yet. Please register first." tone={Palette.info} />
                  <Button title="Register now" onPress={register} />
                </>
              ) : (
                <Button title={busy ? 'Please wait…' : 'Send code'} disabled={busy || mobile.trim().length < 10} onPress={sendCode} />
              )}
              <View className="mt-2 flex-row items-center justify-center gap-1">
                <Text className="font-inter text-sm text-subtle">{t('New to the samaj app?')}</Text>
                <Button title="Register" variant="outlined" small onPress={register} />
              </View>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
