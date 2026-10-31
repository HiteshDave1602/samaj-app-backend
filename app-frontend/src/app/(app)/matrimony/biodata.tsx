import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, Field, Notice, ScreenHeader } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api } from '@/lib/api';
import { label, tWords, useT } from '@/lib/i18n';

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

/** No params: edit my own biodata (PUT replaces it). ?profile=<id>: read someone's after they accepted my request. */
export default function BiodataScreen() {
  const t = useT();
  const { profile } = useLocalSearchParams<{ profile?: string }>();
  const [data, setData] = useState<Biodata>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    api<Biodata>(profile ? `/member/matrimony/profiles/${profile}/biodata` : '/member/matrimony/biodata').then(
      setData,
      // my own: 404 until the first save, so start empty
      (e) => (profile ? setError(e.message) : setData({})),
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
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!data)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Biodata" back />
        <View className="p-5">
          {error ? <Notice title="Could not load biodata" body={error} tone={Palette.rejected} /> : <ActivityIndicator />}
        </View>
      </SafeAreaView>
    );

  if (profile)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <ScreenHeader title="Biodata" back />
        <ScrollView contentContainerStyle={{ padding: 20, paddingTop: 4 }}>
          <View className="rounded-3xl border border-line bg-white p-5">
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
  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="My biodata" back />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} className="flex-1">
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
          <Notice title="Private" body="Only members whose biodata request you accept can see this." tone={Palette.info} />
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
                keyboardType={numeric ? 'number-pad' : undefined}
              />
            ),
          )}
          {error && <Notice title="Could not save" body={error} tone={Palette.rejected} />}
          <Button title={busy ? 'Saving…' : 'Save biodata'} disabled={busy} onPress={save} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
