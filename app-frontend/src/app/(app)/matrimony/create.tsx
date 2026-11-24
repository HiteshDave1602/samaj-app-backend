import { Image } from 'expo-image';
import { router, useFocusEffect } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, Field, Notice, Problem, ScreenHeader, StatusView, UploadBox } from '@/components/ui/form';
import { api, authedImage, upload } from '@/lib/api';
import { label, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';
import { firstError, rules } from '@/lib/validate';

// backend member/matrimony/schema.py ManagedBy / EducationLevel / FamilyBackground and MyProfileOut
const MANAGED_BY = { Self: 'SELF', Parent: 'PARENT', Sibling: 'SIBLING', Relative: 'RELATIVE' } as const;
const EDUCATION = {
  School: 'SCHOOL', Diploma: 'DIPLOMA', Graduate: 'GRADUATE', Postgraduate: 'POSTGRADUATE', Doctorate: 'DOCTORATE', Other: 'OTHER',
} as const;
const BACKGROUND = { Joint: 'JOINT', Nuclear: 'NUCLEAR', Other: 'OTHER' } as const;
const key = <T extends Record<string, string>>(m: T, v: string | null) => (Object.keys(m) as (keyof T)[]).find((k) => m[k] === v);

type Photo = { photo_id: string; status: 'PENDING' | 'APPROVED' | 'REJECTED'; rejection_reason: string | null; file_url: string };
type MyProfile = {
  managed_by: string;
  education_level: string;
  education_detail: string | null;
  occupation: string | null;
  gotra: string | null;
  height_cm: number | null;
  family_background: string;
  about: string | null;
  status: 'DRAFT' | 'PENDING_MODERATION' | 'APPROVED' | 'REJECTED' | 'ARCHIVED';
  moderation_reason: string | null;
  photos: Photo[];
  has_biodata: boolean;
};

const STATUS: Record<MyProfile['status'], { title: string; body: string; tone: 'info' | 'pending' | 'approved' | 'rejected' }> = {
  DRAFT: { title: 'Draft', body: 'Add at least one photo, then submit it for review.', tone: 'info' },
  PENDING_MODERATION: { title: 'Under review', body: 'Your city admin is reviewing your profile.', tone: 'pending' },
  APPROVED: { title: 'Live', body: 'Approved: other members can find your profile.', tone: 'approved' },
  REJECTED: { title: 'Not approved', body: 'Fix the profile and submit again.', tone: 'rejected' },
  ARCHIVED: { title: 'Archived', body: 'This profile is no longer listed.', tone: 'info' },
};

// One screen for the member's own profile: create (POST) the first time, then edit (PUT), photos and submit.
export default function MyMatrimonyProfile() {
  const palette = usePalette();
  const t = useT();
  const [profile, setProfile] = useState<MyProfile | null>(); // null: none yet
  const [form, setForm] = useState({ educationDetail: '', occupation: '', gotra: '', height: '', about: '' });
  const [managedBy, setManagedBy] = useState<keyof typeof MANAGED_BY>('Self');
  const [education, setEducation] = useState<keyof typeof EDUCATION>();
  const [background, setBackground] = useState<keyof typeof BACKGROUND>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false); // just submitted: show the waiting screen
  const [loaded, setLoaded] = useState(form); // as saved: a stored value the rules now refuse is flagged at once
  const set = (k: keyof typeof form) => (v: string) => setForm({ ...form, [k]: v });
  const stale = (k: keyof typeof form) => !!loaded[k] && form[k] === loaded[k];

  const fill = useCallback((p: MyProfile) => {
    setProfile(p);
    const f = { educationDetail: p.education_detail ?? '', occupation: p.occupation ?? '', gotra: p.gotra ?? '', height: p.height_cm?.toString() ?? '', about: p.about ?? '' };
    setForm(f);
    setLoaded(f);
    setManagedBy(key(MANAGED_BY, p.managed_by) ?? 'Self');
    setEducation(key(EDUCATION, p.education_level));
    setBackground(key(BACKGROUND, p.family_background));
  }, []);

  useFocusEffect(
    useCallback(() => {
      // 404 just means "no profile yet"
      api<MyProfile>('/member/matrimony/profile').then(fill, () => setProfile(null));
    }, [fill]),
  );

  async function run(p: Promise<MyProfile>) {
    setBusy(true);
    setError(undefined);
    try {
      const saved = await p;
      fill(saved);
      return saved;
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const body = {
    managed_by: MANAGED_BY[managedBy],
    education_level: education && EDUCATION[education],
    family_background: background && BACKGROUND[background],
    education_detail: form.educationDetail.trim() || null,
    occupation: form.occupation.trim() || null,
    gotra: form.gotra.trim() || null,
    height_cm: form.height.trim() ? Number(form.height) : null,
    about: form.about.trim() || null,
  };
  const errors = {
    educationDetail: rules.text(form.educationDetail, { max: 120 }),
    occupation: rules.text(form.occupation, { max: 80 }),
    gotra: rules.text(form.gotra, { max: 60 }),
    height: rules.height(form.height),
    about: rules.text(form.about, { max: 500, multiline: true }),
  };
  const save = () =>
    run(api<MyProfile>('/member/matrimony/profile', { method: profile ? 'PUT' : 'POST', body }));

  if (profile === undefined)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Matrimonial profile" back />
        <ActivityIndicator className="mt-8" color={palette.secondary.DEFAULT} />
      </SafeAreaView>
    );

  if (sent)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <StatusView
          icon={{ ios: 'checkmark.seal.fill', android: 'verified', web: 'verified' }}
          title="Profile sent for approval"
          body="Your city admin will review it. Once approved, other members can find your profile."
          action="Back to matrimony"
          onAction={() => router.back()}
        />
      </SafeAreaView>
    );

  const status = profile && STATUS[profile.status];
  const canSubmit = profile && (profile.status === 'DRAFT' || profile.status === 'REJECTED');

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Matrimonial profile" back />
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
        {status && (
          <Notice title={status.title} body={profile.moderation_reason ?? status.body} tone={palette[status.tone]} />
        )}
        <Text className="font-inter text-sm text-subtle">{t('Your name, gender and age come from your member profile.')}</Text>
        <Chips
          label="Profile managed by"
          options={Object.keys(MANAGED_BY) as (keyof typeof MANAGED_BY)[]}
          value={managedBy}
          onChange={setManagedBy}
        />
        <Chips label="Education" options={Object.keys(EDUCATION) as (keyof typeof EDUCATION)[]} value={education} onChange={setEducation} />
        <Field label="Degree / course" value={form.educationDetail} onChangeText={set('educationDetail')} placeholder="e.g. B.Tech, Computer Engineering" maxLength={120} error={errors.educationDetail} showError={stale('educationDetail')} />
        <Field label="Occupation" value={form.occupation} onChangeText={set('occupation')} placeholder="e.g. Software Engineer" maxLength={80} error={errors.occupation} showError={stale('occupation')} />
        <Field label="Gotra / Kula" value={form.gotra} onChangeText={set('gotra')} placeholder="e.g. Bharadwaja" maxLength={60} error={errors.gotra} showError={stale('gotra')} />
        <Field label="Height (cm)" value={form.height} onChangeText={set('height')} placeholder="e.g. 168" keyboardType="number-pad" maxLength={3} error={errors.height} showError={stale('height')} />
        <Chips
          label="Family background"
          options={Object.keys(BACKGROUND) as (keyof typeof BACKGROUND)[]}
          value={background}
          onChange={setBackground}
        />
        <Field label="About" value={form.about} onChangeText={set('about')} placeholder="A few lines about yourself" multiline maxLength={500} error={errors.about} showError={stale('about')} />
        <Button
          title={busy ? 'Saving…' : profile ? 'Save changes' : 'Next'} // first save: photos, biodata and submit follow below
          disabled={busy || !education || !background || !!firstError(...Object.values(errors))}
          onPress={save}
        />

        {/* photos and biodata hang off an existing profile */}
        {profile && (
          <>
            <Text className="font-headline text-xl text-brand">{t('Photos')}</Text>
            <View className="flex-row flex-wrap gap-3">
              {profile.photos.map((ph) => (
                <View key={ph.photo_id} className="w-24">
                  <Image source={authedImage(ph.file_url)} style={{ width: 96, height: 120, borderRadius: 16 }} />
                  <Pressable
                    onPress={() => run(api(`/member/matrimony/photos/${ph.photo_id}`, { method: 'DELETE' }))}
                    accessibilityRole="button"
                    accessibilityLabel={t('Remove photo')}
                    hitSlop={8}
                    className="absolute right-1 top-1 rounded-full bg-card p-1">
                    <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={14} tintColor={palette.ink} />
                  </Pressable>
                  <Text numberOfLines={2} className="mt-1 font-inter text-[11px] text-muted">
                    {ph.status === 'REJECTED' ? `${t('Rejected')}${ph.rejection_reason ? `: ${ph.rejection_reason}` : ''}` : label(ph.status)}
                  </Text>
                </View>
              ))}
            </View>
            {profile.photos.length < 5 && (
              <UploadBox
                label="Add photo"
                hint={t('JPG or PNG, 2 MB · {n} left', { n: 5 - profile.photos.length })}
                onPick={(f) => run(upload<MyProfile>('/member/matrimony/photos', 'POST', f))}
              />
            )}

            <Pressable
              onPress={() => router.push('/matrimony/biodata')}
              accessibilityRole="button"
              className="flex-row items-center justify-between rounded-3xl border border-line bg-card p-4 active:opacity-80">
              <View className="flex-1">
                <Text className="font-inter-semibold text-base text-ink">{t('Biodata')}</Text>
                <Text className="font-inter text-sm text-subtle">
                  {t(profile.has_biodata ? 'Filled in · private until you accept a request' : 'Not filled in yet')}
                </Text>
              </View>
              <Text className="font-inter-semibold text-sm text-primary">{t(profile.has_biodata ? 'Edit' : 'Add')}</Text>
            </Pressable>

            {canSubmit && (
              <Button
                title="Submit for review"
                disabled={busy}
                onPress={() => run(api<MyProfile>('/member/matrimony/profile/submit', { method: 'POST' })).then((p) => p && setSent(true))}
              />
            )}
          </>
        )}
        <Problem title="Something went wrong" error={error} />
      </ScrollView>
    </SafeAreaView>
  );
}
