import { router, useLocalSearchParams } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, LayoutAnimation, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BrandHeader, Credits } from '@/components/brand';
import { Button, Chips, DateField, Field, Notice, OtpStatus, useCountdown } from '@/components/ui/form';
import { api, isoDate, parseDmy, saveSession, type OtpSent, type Session } from '@/lib/api';
import { getLang, useLoc, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';
import { BLOOD, MARITAL, rules, type Blood, type Marital } from '@/lib/validate';

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
  const palette = usePalette();
  const t = useT();
  const place = useLoc();
  // ticket: number already verified (older login flow); otherwise mobile comes pre-filled from login and the code is
  // asked once, at submit, after the form is filled
  const params = useLocalSearchParams<{ ticket?: string; mobile?: string }>();
  // 10 digits only; a number carried over from login may have spaces or +91, so keep its last 10 digits
  const [mobile, setMobile] = useState((params.mobile ?? '').replace(/\D/g, '').slice(-10));
  const [code, setCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [shownCode, setShownCode] = useState<string>();
  const [left, startCountdown] = useCountdown();
  const expired = codeSent && !left; // the submit button resends instead
  const [taken, setTaken] = useState(false); // the number already has an account
  const [cities, setCities] = useState<City[]>([]);
  const [form, setForm] = useState({
    name: '', dob: '', family: '', native: '', address: '', gotra: '', education: '', occupation: '', hobby: '',
  });
  const [gender, setGender] = useState<GenderLabel>();
  const [marital, setMarital] = useState<Marital>();
  const [blood, setBlood] = useState<Blood>();
  const [cityId, setCityId] = useState<string>(); // by id: the name changes with the language
  const [cityText, setCityText] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const set = (k: keyof typeof form) => (v: string) => setForm({ ...form, [k]: v });

  useEffect(() => {
    api<City[]>('/member/auth/cities').then(setCities, (e) => setError(e.message));
  }, []);

  const city = cities.find((c) => c.city_id === cityId);
  const cityName = (c: City) => place(c.name, c.name_i18n)!;
  const q = cityText.trim().toLowerCase();
  // matches the English or the shown (Gujarati/Hindi) name, so either script works
  const citySuggestions = !q || city ? [] : cities
    .filter((c) => c.name.toLowerCase().includes(q) || cityName(c).toLowerCase().includes(q))
    .slice(0, 6);
  const optional = (v: string) => v.trim() || null;
  const errors = {
    mobile: params.ticket ? '' : rules.mobile(mobile),
    name: rules.personName(form.name, { required: true }),
    family: rules.personName(form.family, { required: true }),
    native: rules.place(form.native),
    address: rules.text(form.address, { required: true, max: 500, multiline: true }),
    gotra: rules.text(form.gotra, { max: 120 }),
    education: rules.text(form.education, { max: 120 }),
    occupation: rules.text(form.occupation, { max: 120 }),
    hobby: rules.text(form.hobby, { max: 200 }),
  };
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
  const ready = missing.length === 0 && !Object.values(errors).some(Boolean);

  async function submit() {
    setBusy(true);
    setError(undefined);
    try {
      let ticket = params.ticket;
      if (!ticket) {
        if (!codeSent || expired) {
          let r: OtpSent;
          try {
            r = await api<OtpSent>('/member/auth/otp/send', { method: 'POST', body: { mobile, intent: 'register' } });
          } catch (e) {
            if ((e as { status?: number }).status === 409) return setTaken(true);
            throw e;
          }
          LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut); // code field slides in
          setShownCode(r.code);
          startCountdown(r.expires_in_seconds);
          setCode('');
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
          native_place: optional(form.native),
          address: form.address,
          gotra: optional(form.gotra),
          education: optional(form.education),
          marital_status: marital ?? null,
          occupation: optional(form.occupation),
          hobby: optional(form.hobby),
          blood_group: blood ?? null,
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
      <KeyboardAvoidingView behavior="padding" className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }}>
          <BrandHeader size="compact" back />
          <Text className="text-center font-headline text-2xl text-brand">{t('Join your samaj')}</Text>
          <View className="flex-1 gap-[18px] px-5 pb-4 pt-3">
            {!params.ticket && (
              <Field
                label="Mobile number"
                value={mobile}
                onChangeText={(v) => (setMobile(v.replace(/\D/g, '').slice(0, 10)), setCodeSent(false), setTaken(false))}
                maxLength={10}
                editable={!codeSent || expired} // locked while its code is live
                style={codeSent && !expired ? { opacity: 0.6 } : undefined}
                placeholder="9876543210"
                keyboardType="number-pad"
                autoComplete="tel"
                hint="Indian numbers need no +91"
                error={errors.mobile}
              />
            )}
            <Field label="Full name" value={form.name} onChangeText={set('name')} placeholder="As on your ID" autoComplete="name" maxLength={120} error={errors.name} />
            <Chips label="Gender" options={Object.keys(GENDERS) as GenderLabel[]} value={gender} onChange={setGender} />
            <DateField label="Date of birth" value={form.dob} onChange={set('dob')} />
            <View>
              <Field
                label="City"
                value={city ? cityName(city) : cityText}
                onChangeText={(v) => (setCityText(v), setCityId(undefined))} // typing again reopens the list
                placeholder="Start typing your city"
                maxLength={120}
                autoCorrect={false}
                hint={q && !city && !citySuggestions.length ? 'No matching city' : undefined}
              />
              {citySuggestions.length > 0 && (
                <View className="mt-1 overflow-hidden rounded-2xl border border-line bg-card">
                  {citySuggestions.map((c) => (
                    <Pressable
                      key={c.city_id}
                      onPress={() => (setCityId(c.city_id), setCityText(cityName(c)))}
                      accessibilityRole="button"
                      className="border-b border-line px-4 py-3 active:opacity-60">
                      <Text className="font-inter text-base text-ink">{cityName(c)}</Text>
                      <Text className="font-inter text-xs text-muted">{c.state}</Text>
                    </Pressable>
                  ))}
                </View>
              )}
            </View>
            <Field label="Family name" value={form.family} onChangeText={set('family')} placeholder="e.g. Patel" maxLength={120} error={errors.family} />
            <Field label="Native place (optional)" value={form.native} onChangeText={set('native')} placeholder="e.g. Visnagar" maxLength={120} error={errors.native} />
            <Field label="Address" value={form.address} onChangeText={set('address')} placeholder="House, street, area" multiline maxLength={500} error={errors.address} />
            <Field label="Gotra / Vatan (optional)" value={form.gotra} onChangeText={set('gotra')} maxLength={120} error={errors.gotra} />
            <Chips label="Marital status (optional)" options={MARITAL} value={marital} onChange={setMarital} />
            <Field label="Education (optional)" value={form.education} onChangeText={set('education')} placeholder="e.g. B.Com" maxLength={120} error={errors.education} />
            <Field label="Occupation (optional)" value={form.occupation} onChangeText={set('occupation')} placeholder="e.g. Business" maxLength={120} error={errors.occupation} />
            <Chips label="Blood group (optional)" options={BLOOD} value={blood} onChange={setBlood} display={(b) => b} />
            <Field label="Hobby (optional)" value={form.hobby} onChangeText={set('hobby')} placeholder="e.g. Reading, cricket" maxLength={200} error={errors.hobby} />

            <Pressable
              onPress={() => setConsent(!consent)}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: consent }}
              className="flex-row gap-3 rounded-2xl border border-line bg-card p-4">
              <SymbolView
                name={{
                  ios: consent ? 'checkmark.square.fill' : 'square',
                  android: consent ? 'check_box' : 'check_box_outline_blank',
                  web: consent ? 'check_box' : 'check_box_outline_blank',
                }}
                size={24}
                tintColor={consent ? palette.primary.DEFAULT : palette.muted}
              />
              <Text className="flex-1 font-inter text-sm leading-5 text-subtle">{t(NOTICE)}</Text>
            </Pressable>

            {taken && (
              <>
                <Notice title="Already registered" body="This number already has an account. Please log in." tone={palette.info} />
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
            {codeSent && <OtpStatus code={shownCode} left={left} />}
            {error && <Notice title="Could not register" body={error} tone={palette.rejected} />}
            {!ready && <Text className="font-inter text-sm text-subtle">{t('Still needed: {fields}', { fields: missing.map((m) => t(m)).join(', ') })}</Text>}
            <Button
              title={busy ? 'Submitting…' : expired ? 'Resend code' : codeSent ? 'Verify and submit' : 'Submit for approval'}
              disabled={busy || !ready || taken || (codeSent && !expired && code.length !== 6)}
              onPress={submit}
            />
            <View className="h-4" />
            <Credits />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
