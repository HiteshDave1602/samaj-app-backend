import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, ScrollView, Switch, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, DateField, Field, Notice, ScreenHeader, UploadBox } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, dmyDate, isoDate, mediaUrl, parseDmy, restoreSession, upload } from '@/lib/api';
import { LANGUAGES, useLang, useT } from '@/lib/i18n';

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
  const t = useT();
  const [me, setMe] = useState<Me>();
  const [form, setForm] = useState({ name: '', dob: '', address: '', family: '', native: '', nameLoc: '', familyLoc: '', nativeLoc: '' });
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
    });
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

  async function save() {
    if (!me) return;
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
          {error ? <Notice title="Could not load your profile" body={error} tone={Palette.rejected} /> : <ActivityIndicator />}
        </View>
      </SafeAreaView>
    );

  const toggle = (k: keyof typeof flags, title: string) => (
    <View className="flex-row items-center justify-between py-1">
      <Text className="font-inter text-base text-ink">{t(title)}</Text>
      <Switch
        value={flags[k]}
        onValueChange={(v) => setFlags({ ...flags, [k]: v })}
        trackColor={{ true: Palette.primary.DEFAULT }}
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
          <Field label="Full name" value={form.name} onChangeText={set('name')} autoComplete="name" />
          {lang && (
            <Field
              label={t('Full name in {language}', { language: LANGUAGES[lang] })}
              value={form.nameLoc}
              onChangeText={set('nameLoc')}
              hint="Filled in automatically. Fix the spelling if it's wrong."
            />
          )}
          <Chips label="Gender" options={Object.keys(GENDERS) as GenderLabel[]} value={gender} onChange={setGender} />
          <DateField label="Date of birth" value={form.dob} onChange={set('dob')} />
          <Field label="Address" value={form.address} onChangeText={set('address')} multiline maxLength={500} />
          {me.is_household_head && (
            <>
              <Field label="Family name" value={form.family} onChangeText={set('family')} />
              {lang && (
                <Field
                  label={t('Family name in {language}', { language: LANGUAGES[lang] })}
                  value={form.familyLoc}
                  onChangeText={set('familyLoc')}
                />
              )}
              <Field label="Native place (optional)" value={form.native} onChangeText={set('native')} />
              {lang && form.native.trim() !== '' && (
                <Field
                  label={t('Native place in {language}', { language: LANGUAGES[lang] })}
                  value={form.nativeLoc}
                  onChangeText={set('nativeLoc')}
                />
              )}
            </>
          )}

          <View className="rounded-3xl border border-line bg-white p-4">
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

          {error && <Notice title="Could not save" body={error} tone={Palette.rejected} />}
          {saved && <Notice title={saved} body="Your changes are on the server." tone={Palette.approved} />}
          <Button title={busy ? 'Saving…' : 'Save changes'} disabled={busy} onPress={save} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
