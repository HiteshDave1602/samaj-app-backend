import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, DateField, Field, Notice, Problem, ScreenHeader, StatusView } from '@/components/ui/form';
import { api, isoDate, parseDmy } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { BLOOD, MARITAL, rules, type Blood, type Marital } from '@/lib/validate';

// backend member/family/schema.py Relationship (to the household head) and auth Gender
const RELATIONS = {
  Spouse: 'SPOUSE', Son: 'SON', Daughter: 'DAUGHTER', Father: 'FATHER', Mother: 'MOTHER', Brother: 'BROTHER',
  Sister: 'SISTER', Grandfather: 'GRANDFATHER', Grandmother: 'GRANDMOTHER', Grandson: 'GRANDSON',
  Granddaughter: 'GRANDDAUGHTER', 'Son-in-law': 'SON_IN_LAW', 'Daughter-in-law': 'DAUGHTER_IN_LAW', Other: 'OTHER',
} as const;
const GENDERS = { Male: 'MALE', Female: 'FEMALE', Other: 'OTHER' } as const;

export default function AddMember() {
  const t = useT();
  const [form, setForm] = useState({
    name: '', dob: '', mobile: '', address: '', gotra: '', education: '', occupation: '', hobby: '',
  });
  const [relation, setRelation] = useState<keyof typeof RELATIONS>();
  const [relText, setRelText] = useState('');
  // matches the English or the shown (Gujarati/Hindi) label, so either script works
  const rq = relText.trim().toLowerCase();
  const relSuggestions = !rq || relation ? [] : (Object.keys(RELATIONS) as (keyof typeof RELATIONS)[])
    .filter((r) => r.toLowerCase().includes(rq) || t(r).toLowerCase().includes(rq));
  const [gender, setGender] = useState<keyof typeof GENDERS>();
  const [marital, setMarital] = useState<Marital>();
  const [blood, setBlood] = useState<Blood>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false);
  const set = (k: keyof typeof form) => (v: string) => setForm({ ...form, [k]: v });
  const optional = (v: string) => v.trim() || null;
  const dobOk = !!parseDmy(form.dob); // a real past date, not just the DD/MM/YYYY shape
  const errors = {
    name: rules.personName(form.name, { required: true }),
    mobile: form.mobile ? rules.mobile(form.mobile) : '',
    address: rules.text(form.address, { max: 500, multiline: true }),
    gotra: rules.text(form.gotra, { max: 120 }),
    education: rules.text(form.education, { max: 120 }),
    occupation: rules.text(form.occupation, { max: 120 }),
    hobby: rules.text(form.hobby, { max: 200 }),
  };

  async function send() {
    setBusy(true);
    setError(undefined);
    try {
      await api('/member/family', {
        method: 'POST',
        body: {
          full_name: form.name,
          relationship: RELATIONS[relation!],
          gender: GENDERS[gender!],
          dob: isoDate(form.dob),
          mobile: optional(form.mobile),
          address: optional(form.address),
          gotra: optional(form.gotra),
          education: optional(form.education),
          marital_status: marital ?? null,
          occupation: optional(form.occupation),
          hobby: optional(form.hobby),
          blood_group: blood ?? null,
        },
      });
      setSent(true);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView className="flex-1 bg-cream">
      {sent ? (
        <StatusView
          icon={{ ios: 'person.badge.clock.fill', android: 'pending', web: 'pending' }}
          title="Request sent"
          body={t('{name} will appear in your family tree once your city admin approves.', { name: form.name.trim() })}
          action="Back to profile"
          onAction={() => router.back()}
        />
      ) : (
        <KeyboardAvoidingView behavior="padding" className="flex-1">
          <ScreenHeader title="Add family member" back />
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
            <Field label="Name of the member" value={form.name} onChangeText={set('name')} placeholder="Full name" maxLength={120} error={errors.name} />
            <View>
              <Field
                label="Relation to the head of family"
                value={relation ? t(relation) : relText}
                onChangeText={(v) => (setRelText(v), setRelation(undefined))} // typing again reopens the list
                placeholder="Start typing, e.g. Son"
                maxLength={40}
                autoCorrect={false}
                error={rq && !relation && !relSuggestions.length ? t('Pick a relation from the list') : ''}
              />
              {relSuggestions.length > 0 && (
                <View className="mt-1 overflow-hidden rounded-2xl border border-line bg-card">
                  {relSuggestions.map((r) => (
                    <Pressable
                      key={r}
                      onPress={() => (setRelation(r), setRelText(t(r)))}
                      accessibilityRole="button"
                      className="border-b border-line px-4 py-3 active:opacity-60">
                      <Text className="font-inter text-base text-ink">{t(r)}</Text>
                    </Pressable>
                  ))}
                </View>
              )}
            </View>
            <Chips label="Gender" options={Object.keys(GENDERS) as (keyof typeof GENDERS)[]} value={gender} onChange={setGender} />
            <DateField label="Date of birth" value={form.dob} onChange={set('dob')} />
            <Field
              label="Mobile number (optional)"
              value={form.mobile}
              onChangeText={(v) => set('mobile')(v.replace(/\D/g, '').slice(0, 10))}
              maxLength={10}
              placeholder="9876543210"
              keyboardType="number-pad"
              error={errors.mobile}
            />
            <Field label="Address (optional)" value={form.address} onChangeText={set('address')} placeholder="House, street, area" multiline maxLength={500} error={errors.address} />
            <Field label="Gotra / Vatan (optional)" value={form.gotra} onChangeText={set('gotra')} maxLength={120} error={errors.gotra} />
            <Chips label="Marital status (optional)" options={MARITAL} value={marital} onChange={setMarital} />
            <Field label="Education (optional)" value={form.education} onChangeText={set('education')} placeholder="e.g. B.Com" maxLength={120} error={errors.education} />
            <Field label="Occupation (optional)" value={form.occupation} onChangeText={set('occupation')} placeholder="e.g. Business" maxLength={120} error={errors.occupation} />
            <Chips label="Blood group (optional)" options={BLOOD} value={blood} onChange={setBlood} display={(b) => b} />
            <Field label="Hobby (optional)" value={form.hobby} onChangeText={set('hobby')} placeholder="e.g. Reading, cricket" maxLength={200} error={errors.hobby} />
            <Notice title="Needs approval" body="Your city admin will review before it appears in the family tree." />
            <Problem title="Could not send request" error={error} />
            <Button
              title={busy ? 'Sending…' : 'Send request'}
              disabled={busy || Object.values(errors).some(Boolean) || !relation || !gender || !dobOk}
              onPress={send}
            />
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}
