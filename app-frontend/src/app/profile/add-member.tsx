import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, Field, Notice, ScreenHeader, StatusView } from '@/components/ui/form';
import { RELATIONS } from '@/constants/sample-data';

const GENDERS = ['Male', 'Female', 'Other'] as const;

export default function AddMember() {
  const [name, setName] = useState('');
  const [relation, setRelation] = useState<(typeof RELATIONS)[number]>();
  const [gender, setGender] = useState<(typeof GENDERS)[number]>();
  const [dob, setDob] = useState('');
  const [sent, setSent] = useState(false);
  const dobOk = !dob || /^\d{2}\/\d{2}\/\d{4}$/.test(dob);

  return (
    <SafeAreaView className="flex-1 bg-cream">
      {sent ? (
        <StatusView
          icon={{ ios: 'person.badge.clock.fill', android: 'pending', web: 'pending' }}
          title="Request sent"
          body={`${name.trim()} will appear in your family tree once your city admin approves.`}
          action="Back to profile"
          onAction={() => router.back()}
        />
      ) : (
        <>
          <ScreenHeader title="Add family member" back />
          {/* ponytail: submit only shows the sent state until the family_member API exists */}
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
            <Field label="Name of the member" value={name} onChangeText={setName} placeholder="Full name" maxLength={120} />
            <Chips label="Relation" options={RELATIONS} value={relation} onChange={setRelation} />
            <Chips label="Gender" options={GENDERS} value={gender} onChange={setGender} />
            <Field
              label="Date of birth"
              value={dob}
              onChangeText={setDob}
              placeholder="DD/MM/YYYY"
              keyboardType="numbers-and-punctuation"
              maxLength={10}
              hint={dobOk ? undefined : 'Use DD/MM/YYYY'}
            />
            <Notice
              title="Needs approval"
              body="Your city admin will review before it appears in the family tree."
            />
            <Button title="Send request" disabled={!name.trim() || !relation || !dobOk} onPress={() => setSent(true)} />
          </ScrollView>
        </>
      )}
    </SafeAreaView>
  );
}
