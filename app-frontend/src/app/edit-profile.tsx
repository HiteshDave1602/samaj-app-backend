import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, ScrollView, Switch, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, DateField, Field, Notice, ScreenHeader, UploadBox } from '@/components/ui/form';
import { api, dmyDate, isoDate, mediaUrl, parseDmy, restoreSession, upload } from '@/lib/api';
import { LANGUAGES, useLang, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';
import { BLOOD, MARITAL, rules, type Blood, type Marital } from '@/lib/validate';

// backend member/profile/schema.py MemberOut (the editable part) and MemberUpdate
type Me = {
  full_name: string | null;
  full_name_i18n: Record<string, string>;
  gender: string | null;
  dob: string | null;
  address: string | null;
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
  is_household_head: boolean;
  status: 'PENDING' | 'ACTIVE' | 'REJECTED' | 'ARCHIVED';
  hide_phone: boolean;
  hide_address: boolean;
  notify_news: boolean;
  id_document: { uploaded_at?: string } | null;
  photo_url: string | null;
};
const GENDERS = { Male: 'MALE', Female: 'FEMALE', Other: 'OTHER' } as const;
type GenderLabel = keyof typeof GENDERS;
const genderLabel = (v: string | null) => (Object.keys(GENDERS) as GenderLabel[]).find((k) => GENDERS[k] === v);

// Outside the (app) gate on purpose: pending and rejected members fix their details and ID document here.
export default function EditProfile() {
  const palette = usePalette();
  const t = useT();
  const [me, setMe] = useState<Me>();
  const [form, setForm] = useState({
    name: '', dob: '', address: '', family: '', native: '', nameLoc: '', familyLoc: '', nativeLoc: '',
    gotra: '', education: '', occupation: '', hobby: '',
  });
  const [marital, setMarital] = useState<Marital>();
  const [blood, setBlood] = useState<Blood>();
  // English has no spellings to correct; gu/hi edit the auto-transliterated ones
  const current = useLang();
  const lang = current === 'en' ? undefined : current;
  const [gender, setGender] = useState<GenderLabel>();
  const [flags, setFlags] = useState({ hide_phone: false, hide_address: false, notify_news: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState<string>();
  const set = (k: keyof typeof form) => (v: string) => setForm({ ...form, [k]: v });

  function fill(m: Me) {
    setMe(m);
    setForm({
      name: m.full_name ?? '',
      dob: m.dob ? dmyDate(m.dob) : '',
      address: m.address ?? '',
      family: m.family_name ?? '',
      native: m.native_place ?? '',
      nameLoc: (lang && m.full_name_i18n[lang]) ?? '',
      familyLoc: (lang && m.family_name_i18n[lang]) ?? '',
      nativeLoc: (lang && m.native_place_i18n[lang]) ?? '',
      gotra: m.gotra ?? '',
      education: m.education ?? '',
      occupation: m.occupation ?? '',
      hobby: m.hobby ?? '',
    });
    // a value the app doesn't offer (e.g. from an import) shows as unselected
    setMarital(MARITAL.find((v) => v === m.marital_status));
    setBlood(BLOOD.find((v) => v === m.blood_group));
    setGender(genderLabel(m.gender));
    setFlags({ hide_phone: m.hide_phone, hide_address: m.hide_address, notify_news: m.notify_news });
  }

  useEffect(() => {
    api<Me>('/member/me').then(fill, (e) => setError(e.message));
  }, []);

  /** A save can move the membership back to review; refresh the session so the gate sees the new status. */
  async function after(m: Me, message: string) {
    fill(m);
    setSaved(message);
    if (m.status !== 'ACTIVE') {
      await restoreSession();
      router.replace('/pending');
    }
  }

  // only what changed is sent, so only what changed is judged: an older stored value never blocks saving the rest
  const changed = (v: string, stored?: string | null) => v.trim() !== (stored ?? '');
  const loc = (m?: Record<string, string>) => (lang && m?.[lang]) || '';
  const errors = {
    name: changed(form.name, me?.full_name) ? rules.personName(form.name, { required: true }) : '',
    nameLoc: changed(form.nameLoc, loc(me?.full_name_i18n)) ? rules.personName(form.nameLoc) : '',
    address: changed(form.address, me?.address) ? rules.text(form.address, { required: true, max: 500, multiline: true }) : '',
    family: me?.is_household_head && changed(form.family, me.family_name) ? rules.personName(form.family, { required: true }) : '',
    familyLoc: changed(form.familyLoc, loc(me?.family_name_i18n)) ? rules.personName(form.familyLoc) : '',
    native: changed(form.native, me?.native_place) ? rules.place(form.native) : '',
    nativeLoc: changed(form.nativeLoc, loc(me?.native_place_i18n)) ? rules.place(form.nativeLoc) : '',
    gotra: changed(form.gotra, me?.gotra) ? rules.text(form.gotra, { max: 120 }) : '',
    education: changed(form.education, me?.education) ? rules.text(form.education, { max: 120 }) : '',
    occupation: changed(form.occupation, me?.occupation) ? rules.text(form.occupation, { max: 120 }) : '',
    hobby: changed(form.hobby, me?.hobby) ? rules.text(form.hobby, { max: 200 }) : '',
  };
  const invalid = Object.values(errors).some(Boolean);

  async function save() {
    if (!me || invalid) return;
    if (form.dob && !parseDmy(form.dob)) return setError(t('Not a valid date'));
    setBusy(true);
    setError(undefined);
    setSaved(undefined);
    // MemberUpdate: send only what changed
    const body: Record<string, unknown> = {};
    if (form.name.trim() !== (me.full_name ?? '')) body.full_name = form.name;
    if (gender && GENDERS[gender] !== me.gender) body.gender = GENDERS[gender];
    if (form.dob && isoDate(form.dob) !== me.dob) body.dob = isoDate(form.dob);
    if (form.address.trim() !== (me.address ?? '')) body.address = form.address;
    if (me.is_household_head) {
      if (form.family.trim() !== (me.family_name ?? '')) body.family_name = form.family;
      if (form.native.trim() !== (me.native_place ?? '')) body.native_place = form.native.trim() || null;
    }
    for (const k of ['gotra', 'education', 'occupation', 'hobby'] as const)
      if (changed(form[k], me[k])) body[k] = form[k].trim() || null; // blank clears it
    if (marital && marital !== me.marital_status) body.marital_status = marital;
    if (blood && blood !== me.blood_group) body.blood_group = blood;
    if (lang) {
      const fix = (v: string, stored: Record<string, string>) => (v.trim() && v.trim() !== stored[lang] ? { [lang]: v } : undefined);
      body.full_name_i18n = fix(form.nameLoc, me.full_name_i18n);
      if (me.is_household_head) {
        body.family_name_i18n = fix(form.familyLoc, me.family_name_i18n);
        body.native_place_i18n = fix(form.nativeLoc, me.native_place_i18n);
      }
      for (const k of ['full_name_i18n', 'family_name_i18n', 'native_place_i18n']) if (!body[k]) delete body[k];
    }
    for (const k of Object.keys(flags) as (keyof typeof flags)[]) if (flags[k] !== me[k]) body[k] = flags[k];
    try {
      const m = await api<Me>('/member/me', { method: 'PUT', body });
      await after(m, 'Saved.');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!me)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Edit profile" back />
        <View className="p-5">
          {error ? <Notice title="Could not load your profile" body={error} tone={palette.rejected} /> : <ActivityIndicator />}
        </View>
      </SafeAreaView>
    );

  const toggle = (k: keyof typeof flags, title: string) => (
    <View className="flex-row items-center justify-between py-1">
      <Text className="font-inter text-base text-ink">{t(title)}</Text>
      <Switch
        value={flags[k]}
        onValueChange={(v) => setFlags({ ...flags, [k]: v })}
        trackColor={{ true: palette.primary.DEFAULT }}
        accessibilityLabel={t(title)}
      />
    </View>
  );

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Edit profile" back />
      <KeyboardAvoidingView behavior="padding" className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
          {me.status === 'ACTIVE' && (
            <Notice title="Heads up" body="Changing your name or date of birth sends your profile back to your city admin for review." />
          )}
          {me.photo_url && (
            <Image
              source={{ uri: mediaUrl(me.photo_url)! }}
              style={{ width: 88, height: 88, borderRadius: 44, alignSelf: 'center' }}
            />
          )}
          {/* a photo never changes the membership status, so no after() redirect */}
          <UploadBox
            label="Profile photo"
            optional
            hint={me.photo_url ? 'Tap to change · JPG or PNG, up to 2 MB' : 'JPG or PNG, up to 2 MB'}
            onPick={(f) =>
              upload<Me>('/member/me/photo', 'PUT', f).then(
                (m) => (fill(m), setSaved('Photo updated.')),
                (e) => setError(e.message),
              )
            }
          />
          <Field label="Full name" value={form.name} onChangeText={set('name')} autoComplete="name" maxLength={120} error={errors.name} />
          {lang && (
            <Field
              label={t('Full name in {language}', { language: LANGUAGES[lang] })}
              value={form.nameLoc}
              onChangeText={set('nameLoc')}
              maxLength={120}
              error={errors.nameLoc}
              hint="Filled in automatically. Fix the spelling if it's wrong."
            />
          )}
          <Chips label="Gender" options={Object.keys(GENDERS) as GenderLabel[]} value={gender} onChange={setGender} />
          <DateField label="Date of birth" value={form.dob} onChange={set('dob')} />
          <Field label="Address" value={form.address} onChangeText={set('address')} multiline maxLength={500} error={errors.address} />
          {me.is_household_head && (
            <>
              <Field label="Family name" value={form.family} onChangeText={set('family')} maxLength={120} error={errors.family} />
              {lang && (
                <Field
                  label={t('Family name in {language}', { language: LANGUAGES[lang] })}
                  value={form.familyLoc}
                  onChangeText={set('familyLoc')}
                  maxLength={120}
                  error={errors.familyLoc}
                />
              )}
              <Field label="Native place (optional)" value={form.native} onChangeText={set('native')} maxLength={120} error={errors.native} />
              {lang && form.native.trim() !== '' && (
                <Field
                  label={t('Native place in {language}', { language: LANGUAGES[lang] })}
                  value={form.nativeLoc}
                  onChangeText={set('nativeLoc')}
                  maxLength={120}
                  error={errors.nativeLoc}
                />
              )}
            </>
          )}
          <Field label="Gotra / Vatan (optional)" value={form.gotra} onChangeText={set('gotra')} maxLength={120} error={errors.gotra} />
          <Chips label="Marital status (optional)" options={MARITAL} value={marital} onChange={setMarital} />
          <Field label="Education (optional)" value={form.education} onChangeText={set('education')} placeholder="e.g. B.Com" maxLength={120} error={errors.education} />
          <Field label="Occupation (optional)" value={form.occupation} onChangeText={set('occupation')} placeholder="e.g. Business" maxLength={120} error={errors.occupation} />
          <Chips label="Blood group (optional)" options={BLOOD} value={blood} onChange={setBlood} display={(b) => b} />
          <Field label="Hobby (optional)" value={form.hobby} onChangeText={set('hobby')} placeholder="e.g. Reading, cricket" maxLength={200} error={errors.hobby} />

          <View className="rounded-3xl border border-line bg-card p-4">
            {toggle('hide_phone', 'Hide my phone in the directory')}
            {toggle('hide_address', 'Hide my address in the directory')}
            {toggle('notify_news', 'Notify me about news')}
          </View>

          {/* the backend takes an ID document only while the membership is pending or rejected */}
          {me.status !== 'ACTIVE' && (
            <UploadBox
              label="ID document"
              hint={me.id_document ? 'Uploaded · tap to replace' : 'JPG, PNG or PDF up to 2 MB'}
              pdf
              onPick={(f) =>
                upload<Me>('/member/me/id-document', 'PUT', f).then(
                  (m) => after(m, 'ID document uploaded.'),
                  (e) => setError(e.message),
                )
              }
            />
          )}

          {error && <Notice title="Could not save" body={error} tone={palette.rejected} />}
          {saved && <Notice title={saved} body="Your changes are on the server." tone={palette.approved} />}
          <Button title={busy ? 'Saving…' : 'Save changes'} disabled={busy || invalid} onPress={save} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
