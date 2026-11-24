import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, LayoutAnimation, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BrandHeader, Credits, useKeyboardOpen } from '@/components/brand';
import { Button, Field, Notice, OtpStatus, useCountdown } from '@/components/ui/form';
import { api, saveSession, type OtpSent, type Session } from '@/lib/api';
import { syncLang, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';
import { rules } from '@/lib/validate';

// no session: not approved yet (member_status PENDING / REJECTED), or no account at all (registered false)
type VerifyOut = { registered: boolean; session?: Session; member_status?: string; rejection_reason?: string };
// The samaj's name as written on its logo, the same in every app language
const ORG = 'શ્રી સુરત અઠ્ઠાવીશી મોઢ ચાતુર્વેદી બ્રાહ્મણ પરિવાર';
const MANDAL = 'પ્રગતિ મંડળ';

// SF-01: the number is checked first, so an unknown number gets "register first" instead of a code. Registering opens
// the form with the number filled in (no code there). Only approved members get past the code; others see /pending.
export default function Login() {
  const palette = usePalette();
  const t = useT();
  const keyboardOpen = useKeyboardOpen();
  const [mobile, setMobile] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false); // false: asking for the number, true: asking for the code
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [unknown, setUnknown] = useState(false); // no account for this number
  const [shownCode, setShownCode] = useState<string>();
  const [left, startCountdown] = useCountdown();

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
      let r: OtpSent;
      try {
        r = await api<OtpSent>('/member/auth/otp/send', { method: 'POST', body: { mobile, intent: 'login' } });
      } catch (e) {
        if ((e as { status?: number }).status === 404) return setUnknown(true);
        throw e;
      }
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut); // number form -> code form
      setShownCode(r.code);
      startCountdown(r.expires_in_seconds);
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
      } else if (r.member_status) {
        // only approved members log in; the rest see where their registration stands
        router.replace({
          pathname: '/pending',
          params: { status: r.member_status, ...(r.rejection_reason && { reason: r.rejection_reason }) },
        });
      } else {
        register(); // no account (e.g. deleted meanwhile): the form, number filled in
      }
    });

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <KeyboardAvoidingView behavior="padding" className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }}>
          {/* keyboard up: a small logo, so the number field and button sit above the keyboard */}
          <BrandHeader size={keyboardOpen ? 'mini' : 'full'} />
          {!keyboardOpen && (
            <View className="items-center px-6">
              <Text className="text-center font-headline text-lg leading-6 text-secondary">{ORG}</Text>
              <Text className="font-headline text-base text-brand">{MANDAL}</Text>
            </View>
          )}
          <View className="flex-1 gap-[18px] px-6 pb-4 pt-5">
            <View>
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
                <OtpStatus code={shownCode} left={left} />
                {error && <Notice title="Could not log in" body={error} tone={palette.rejected} />}
                <Button title={busy ? 'Please wait…' : 'Verify'} disabled={busy || !left || code.length !== 6} onPress={verify} />
                <View className="flex-row justify-between">
                  {/* the number stays locked while its code is live */}
                  {!left && <Button title="Change number" variant="outlined" small onPress={() => (setSent(false), setError(undefined))} />}
                  <Button title="Resend code" variant="outlined" small disabled={busy} onPress={sendCode} />
                </View>
              </>
            ) : (
              <>
                <Field
                  key="mobile"
                  label="Mobile number"
                  value={mobile}
                  // digits only, at most 10; a pasted/autofilled +91 or leading 0 is dropped first
                  onChangeText={(v) => (setMobile(v.replace(/\D/g, '').replace(/^(91|0)(?=\d{10}$)/, '').slice(0, 10)), setUnknown(false))}
                  placeholder="9876543210"
                  keyboardType="number-pad"
                  textContentType="telephoneNumber"
                  autoComplete="tel"
                  hint="Indian numbers need no +91"
                  error={rules.mobile(mobile)}
                />
                {error && <Notice title="Could not send the code" body={error} tone={palette.rejected} />}
                {unknown ? (
                  <>
                    <Notice title="No account found" body="This number is not registered yet. Please register first." tone={palette.info} />
                    <Button title="Register now" onPress={register} />
                  </>
                ) : (
                  <Button title={busy ? 'Please wait…' : 'Send code'} disabled={busy || mobile.trim().length < 10 || !!rules.mobile(mobile)} onPress={sendCode} />
                )}
                <View className="mt-2 flex-row items-center justify-center gap-1">
                  <Text className="font-inter text-sm text-subtle">{t('New to the samaj app?')}</Text>
                  <Button title="Register" variant="outlined" small onPress={register} />
                </View>
              </>
            )}
            <Credits />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
