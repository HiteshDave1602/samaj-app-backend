import { router, useLocalSearchParams } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, DateField, Field, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, isoDate, parseDmy, saveSession, type Session } from '@/lib/api';
import { getLang, useLoc, useT } from '@/lib/i18n';

// Must match NOTICE_VERSION in backend/member/auth/curd.py; bump both when the text below changes.
// ponytail: placeholder wording, swap in the approved consent notice from the PRD
const NOTICE_VERSION = 'v1';
const NOTICE =
  'I agree that my samaj may store my name, mobile number, address and family details to verify my membership, ' +
  'and show them to approved members in the directory. I can hide my phone and address, or ask for my data to be deleted, at any time.';

const GENDERS = { Male: 'MALE', Female: 'FEMALE', Other: 'OTHER' } as const;
type GenderLabel = keyof typeof GENDERS;
type City = { city_id: string; name: string; name_i18n: Record<string, string>; state: string };

export default function Register() {
  const t = useT();
  const place = useLoc();
  // ticket: number already verified (older login flow); otherwise mobile comes pre-filled from login and the code is
  // asked once, at submit, after the form is filled
  const params = useLocalSearchParams<{ ticket?: string; mobile?: string }>();
  const [mobile, setMobile] = useState(params.mobile ?? '');
  const [code, setCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [taken, setTaken] = useState(false); // the number already has an account
  const [cities, setCities] = useState<City[]>([]);
  const [form, setForm] = useState({ name: '', dob: '', family: '', native: '', address: '' });
  const [gender, setGender] = useState<GenderLabel>();
  const [cityId, setCityId] = useState<string>(); // by id: the name changes with the language
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const set = (k: keyof typeof form) => (v: string) => setForm({ ...form, [k]: v });

  useEffect(() => {
    api<City[]>('/member/auth/cities').then(setCities, (e) => setError(e.message));
  }, []);

  // ponytail: city chips suit a handful of cities; switch to a searchable list once there are dozens
  const city = cities.find((c) => c.city_id === cityId);
  const missing = [
    !params.ticket && mobile.trim().length < 10 && 'mobile number',
    !form.name.trim() && 'full name',
    !gender && 'gender',
    !parseDmy(form.dob) && 'a valid date of birth',
    !city && 'city',
    !form.family.trim() && 'family name',
    !form.address.trim() && 'address',
    !consent && 'consent',
  ].filter((m): m is string => !!m);
  const ready = missing.length === 0;

  async function submit() {
    setBusy(true);
    setError(undefined);
    try {
      let ticket = params.ticket;
      if (!ticket) {
        if (!codeSent) {
          try {
            await api('/member/auth/otp/send', { method: 'POST', body: { mobile, intent: 'register' } });
          } catch (e) {
            if ((e as { status?: number }).status === 409) return setTaken(true);
            throw e;
          }
          return setCodeSent(true);
        }
        const r = await api<{ session?: Session; registration_ticket?: string }>('/member/auth/otp/verify', {
          method: 'POST',
          body: { mobile, code },
        });
        if (r.session) {
          // registered from another device meanwhile: just log in
          await saveSession(r.session);
          return router.replace('/home');
        }
        ticket = r.registration_ticket;
      }
      const s = await api<Session>('/member/auth/register', {
        method: 'POST',
        body: {
          registration_ticket: ticket,
          full_name: form.name,
          gender: GENDERS[gender!],
          dob: isoDate(form.dob),
          city_id: city!.city_id,
          family_name: form.family,
          native_place: form.native.trim() || null,
          address: form.address,
          language: getLang(),
          consent: true,
          notice_version: NOTICE_VERSION,
        },
      });
      await saveSession(s);
      router.replace('/pending');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Join your samaj" back />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
          {!params.ticket && (
            <Field
              label="Mobile number"
              value={mobile}
              onChangeText={(v) => (setMobile(v), setCodeSent(false), setTaken(false))}
              placeholder="98765 43210"
              keyboardType="phone-pad"
              autoComplete="tel"
              hint="Indian numbers need no +91"
            />
          )}
          <Field label="Full name" value={form.name} onChangeText={set('name')} placeholder="As on your ID" autoComplete="name" />
          <Chips label="Gender" options={Object.keys(GENDERS) as GenderLabel[]} value={gender} onChange={setGender} />
          <DateField label="Date of birth" value={form.dob} onChange={set('dob')} />
          <Chips
            label="City"
            options={cities.map((c) => c.city_id)}
            display={(id) => {
              const c = cities.find((x) => x.city_id === id)!;
              return place(c.name, c.name_i18n)!;
            }}
            value={cityId}
            onChange={setCityId}
          />
          <Field label="Family name" value={form.family} onChangeText={set('family')} placeholder="e.g. Patel" />
          <Field label="Native place (optional)" value={form.native} onChangeText={set('native')} placeholder="e.g. Visnagar" />
          <Field label="Address" value={form.address} onChangeText={set('address')} placeholder="House, street, area" multiline maxLength={500} />

          <Pressable
            onPress={() => setConsent(!consent)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: consent }}
            className="flex-row gap-3 rounded-2xl border border-line bg-white p-4">
            <SymbolView
              name={{
                ios: consent ? 'checkmark.square.fill' : 'square',
                android: consent ? 'check_box' : 'check_box_outline_blank',
                web: consent ? 'check_box' : 'check_box_outline_blank',
              }}
              size={24}
              tintColor={consent ? Palette.primary.DEFAULT : Palette.muted}
            />
            <Text className="flex-1 font-inter text-sm leading-5 text-subtle">{t(NOTICE)}</Text>
          </Pressable>

          {taken && (
            <>
              <Notice title="Already registered" body="This number already has an account. Please log in." tone={Palette.info} />
              <Button title="Log in instead" variant="outlined" onPress={() => router.replace('/login')} />
            </>
          )}
          {codeSent && (
            <Field
              label={t('Code sent to {mobile}', { mobile: mobile.trim() })}
              value={code}
              onChangeText={(v) => setCode(v.replace(/\D/g, ''))}
              placeholder="6-digit code"
              keyboardType="number-pad"
              textContentType="oneTimeCode"
              autoComplete="sms-otp"
              maxLength={6}
              hint="Enter it to verify your number and submit"
              autoFocus
            />
          )}
          {error && <Notice title="Could not register" body={error} tone={Palette.rejected} />}
          {!ready && <Text className="font-inter text-sm text-subtle">{t('Still needed: {fields}', { fields: missing.map((m) => t(m)).join(', ') })}</Text>}
          <Button
            title={busy ? 'Submitting…' : codeSent ? 'Verify and submit' : 'Submit for approval'}
            disabled={busy || !ready || taken || (codeSent && code.length !== 6)}
            onPress={submit}
          />
          <View className="h-4" />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
