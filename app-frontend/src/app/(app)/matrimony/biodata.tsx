import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, Field, Notice, Problem, ScreenHeader } from '@/components/ui/form';
import { api } from '@/lib/api';
import { label, tWords, useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';
import { rules } from '@/lib/validate';

// backend member/matrimony/schema.py BiodataIn, in display order. `options` fields are enums.
// typed as English words from a known list: shown translated
const WORDS = new Set(['rashi', 'nakshatra', 'gotra']);
const FIELDS: { key: string; title: string; options?: string[]; multiline?: boolean; numeric?: boolean; hint?: string }[] = [
  { key: 'height_cm', title: 'Height (cm)', numeric: true },
  { key: 'diet', title: 'Diet', options: ['VEG', 'NON_VEG', 'EGGETARIAN', 'JAIN', 'VEGAN'] },
  { key: 'birth_time', title: 'Birth time', hint: 'HH:MM, 24-hour' },
  { key: 'birth_place', title: 'Birth place' },
  { key: 'rashi', title: 'Rashi' },
  { key: 'nakshatra', title: 'Nakshatra' },
  { key: 'gotra', title: 'Gotra' },
  { key: 'manglik', title: 'Manglik', options: ['YES', 'NO', 'ANSHIK', 'DONT_KNOW'] },
  { key: 'father_name', title: "Father's name" },
  { key: 'father_occupation', title: "Father's occupation" },
  { key: 'mother_name', title: "Mother's name" },
  { key: 'mother_occupation', title: "Mother's occupation" },
  { key: 'siblings', title: 'Siblings', multiline: true },
  { key: 'annual_income', title: 'Annual income' },
  { key: 'residence_address', title: 'Residence address', multiline: true },
  { key: 'contact_phone', title: 'Contact phone' },
  { key: 'contact_email', title: 'Contact email' },
  { key: 'expectations', title: 'Expectations', multiline: true },
];

type Biodata = Record<string, string | number | undefined>;

// backend BiodataIn limits; every field is optional
const CHECK: Record<string, (v: string) => string> = {
  height_cm: rules.height,
  birth_time: rules.time,
  birth_place: (v) => rules.place(v),
  rashi: (v) => rules.text(v, { max: 40 }),
  nakshatra: (v) => rules.text(v, { max: 40 }),
  gotra: (v) => rules.text(v, { max: 60 }),
  father_name: (v) => rules.personName(v),
  father_occupation: (v) => rules.text(v),
  mother_name: (v) => rules.personName(v),
  mother_occupation: (v) => rules.text(v),
  siblings: (v) => rules.text(v, { max: 300, multiline: true }),
  annual_income: (v) => rules.text(v, { max: 60 }),
  residence_address: (v) => rules.text(v, { max: 500, multiline: true }),
  contact_phone: (v) => rules.mobile(v),
  contact_email: (v) => rules.email(v, { max: 254 }),
  expectations: (v) => rules.text(v, { max: 1000, multiline: true }),
};

/** No params: edit my own biodata (PUT replaces it). ?profile=<id>: read someone's after they accepted my request. */
export default function BiodataScreen() {
  const palette = usePalette();
  const t = useT();
  const { profile } = useLocalSearchParams<{ profile?: string }>();
  const [data, setData] = useState<Biodata>();
  const [saved, setSaved] = useState<Biodata>({}); // as loaded: a stored value the rules now refuse is flagged at once
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    api<Biodata>(profile ? `/member/matrimony/profiles/${profile}/biodata` : '/member/matrimony/biodata').then(
      (b) => (setData(b), setSaved(b)),
      // my own: 404 until the first save, so start empty
      (e) => (profile ? setError(e) : setData({})),
    );
  }, [profile]);

  async function save() {
    setBusy(true);
    setError(undefined);
    const body = Object.fromEntries(
      FIELDS.map(({ key, numeric }) => {
        const v = String(data?.[key] ?? '').trim();
        return [key, v === '' ? null : numeric ? Number(v) : v];
      }),
    );
    try {
      await api('/member/matrimony/biodata', { method: 'PUT', body });
      router.back();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (!data)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Biodata" back />
        <View className="p-5">
          {error ? <Problem title="Could not load biodata" error={error} /> : <ActivityIndicator />}
        </View>
      </SafeAreaView>
    );

  if (profile)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Biodata" back />
        <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4 }}>
          <View className="rounded-3xl border border-line bg-card p-5">
            {FIELDS.filter(({ key }) => data[key] != null).map(({ key, title, options }, i) => (
              <View key={key} className={`py-2.5 ${i ? 'border-t border-line' : ''}`}>
                <Text className="font-inter text-xs text-muted">{t(title)}</Text>
                <Text className="font-inter-semibold text-sm text-ink">
                  {options ? label(String(data[key])) : WORDS.has(key) ? tWords(t, String(data[key]), key === 'nakshatra' ? 'nakshatra' : undefined) : String(data[key])}
                </Text>
              </View>
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    );

  const set = (k: string) => (v: string) => setData({ ...data, [k]: v });
  const errors = Object.fromEntries(FIELDS.map(({ key }) => [key, CHECK[key]?.(String(data[key] ?? '')) ?? '']));
  const invalid = Object.values(errors).some(Boolean);
  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="My biodata" back />
      <KeyboardAvoidingView behavior="padding" className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
          <Notice title="Private" body="Only members whose biodata request you accept can see this." tone={palette.info} />
          {FIELDS.map(({ key, title, options, multiline, numeric, hint }) =>
            options ? (
              <Chips
                key={key}
                label={title}
                options={options.map(label)}
                value={data[key] ? label(String(data[key])) : undefined}
                onChange={(v) => setData({ ...data, [key]: options.find((o) => label(o) === v) })}
              />
            ) : (
              <Field
                key={key}
                label={title}
                value={String(data[key] ?? '')}
                onChangeText={set(key)}
                multiline={multiline}
                hint={hint}
                error={errors[key]}
                showError={saved[key] != null && data[key] === saved[key]}
                keyboardType={numeric ? 'number-pad' : undefined}
              />
            ),
          )}
          <Problem title="Could not save" error={error} />
          <Button title={busy ? 'Saving…' : 'Save biodata'} disabled={busy || invalid} onPress={save} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
