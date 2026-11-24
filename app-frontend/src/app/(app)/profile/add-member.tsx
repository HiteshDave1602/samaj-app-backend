import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, DateField, Field, Notice, Problem, ScreenHeader, StatusView } from '@/components/ui/form';
import { api, isoDate, parseDmy } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { rules } from '@/lib/validate';

// backend member/family/schema.py Relationship (to the household head) and auth Gender
const RELATIONS = {
  Spouse: 'SPOUSE', Son: 'SON', Daughter: 'DAUGHTER', Father: 'FATHER', Mother: 'MOTHER', Brother: 'BROTHER',
  Sister: 'SISTER', Grandfather: 'GRANDFATHER', Grandmother: 'GRANDMOTHER', Grandson: 'GRANDSON',
  Granddaughter: 'GRANDDAUGHTER', 'Son-in-law': 'SON_IN_LAW', 'Daughter-in-law': 'DAUGHTER_IN_LAW', Other: 'OTHER',
} as const;
const GENDERS = { Male: 'MALE', Female: 'FEMALE', Other: 'OTHER' } as const;

export default function AddMember() {
  const t = useT();
  const [name, setName] = useState('');
  const [relation, setRelation] = useState<keyof typeof RELATIONS>();
  const [gender, setGender] = useState<keyof typeof GENDERS>();
  const [dob, setDob] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false);
  const dobOk = !!parseDmy(dob); // a real past date, not just the DD/MM/YYYY shape
  const nameError = rules.personName(name, { required: true });

  async function send() {
    setBusy(true);
    setError(undefined);
    try {
      await api('/member/family', {
        method: 'POST',
        body: { full_name: name, relationship: RELATIONS[relation!], gender: GENDERS[gender!], dob: isoDate(dob) },
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
          body={t('{name} will appear in your family tree once your city admin approves.', { name: name.trim() })}
          action="Back to profile"
          onAction={() => router.back()}
        />
      ) : (
        <>
          <ScreenHeader title="Add family member" back />
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
            <Field label="Name of the member" value={name} onChangeText={setName} placeholder="Full name" maxLength={120} error={nameError} />
            <Chips
              label="Relation to the head of family"
              options={Object.keys(RELATIONS) as (keyof typeof RELATIONS)[]}
              value={relation}
              onChange={setRelation}
            />
            <Chips label="Gender" options={Object.keys(GENDERS) as (keyof typeof GENDERS)[]} value={gender} onChange={setGender} />
            <DateField label="Date of birth" value={dob} onChange={setDob} />
            <Notice title="Needs approval" body="Your city admin will review before it appears in the family tree." />
            <Problem title="Could not send request" error={error} />
            <Button
              title={busy ? 'Sending…' : 'Send request'}
              disabled={busy || !!nameError || !relation || !gender || !dobOk}
              onPress={send}
            />
          </ScrollView>
        </>
      )}
    </SafeAreaView>
  );
}
