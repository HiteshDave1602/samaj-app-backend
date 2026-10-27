import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, Field, Notice, ScreenHeader, StatusView, UploadBox } from '@/components/ui/form';
import { Palette } from '@/constants/theme';

// options mirror the matrimony_profile CHECK constraints in docs/Samaj_schema_v1.0.sql
const MANAGED_BY = ['Self', 'Parent', 'Sibling', 'Relative'] as const;
const EDUCATION = ['School', 'Diploma', 'Graduate', 'Postgraduate', 'Doctorate', 'Other'] as const;

export default function CreateMatrimonyProfile() {
  const [form, setForm] = useState({ name: '', gotra: '', educationDetail: '', profession: '', native: '', family: '', about: '' });
  const [managedBy, setManagedBy] = useState<(typeof MANAGED_BY)[number]>('Self');
  const [education, setEducation] = useState<(typeof EDUCATION)[number]>();
  const [sent, setSent] = useState(false);
  const set = (k: keyof typeof form) => (v: string) => setForm({ ...form, [k]: v });
  const ready = form.name.trim() && form.gotra.trim() && education && form.family.trim();

  return (
    <SafeAreaView className="flex-1 bg-cream">
      {sent ? (
        <StatusView
          icon={{ ios: 'envelope.fill', android: 'mail', web: 'mail' }}
          tone={Palette.secondary}
          title="Sent for approval"
          body="Your city admin will review your profile. Once approved, it appears to other members and we will notify you."
          action="Back to matrimony"
          onAction={() => router.back()}
        />
      ) : (
        <>
          <ScreenHeader title="Matrimonial profile" back />
          {/* ponytail: submit only shows the sent state until the matrimony API exists */}
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
            <Chips label="Profile managed by" options={MANAGED_BY} value={managedBy} onChange={setManagedBy} />
            <Field label="Full name" value={form.name} onChangeText={set('name')} placeholder="As on your ID" />
            <Field label="Gotra" value={form.gotra} onChangeText={set('gotra')} placeholder="e.g. Kashyap" />
            <Chips label="Education" options={EDUCATION} value={education} onChange={setEducation} />
            <Field label="Degree / course" value={form.educationDetail} onChangeText={set('educationDetail')} placeholder="e.g. B.Tech, Computer Engineering" />
            <Field label="Profession" value={form.profession} onChangeText={set('profession')} placeholder="e.g. Software Engineer" />
            <Field label="Native place" value={form.native} onChangeText={set('native')} placeholder="e.g. Visnagar" />
            <Field label="Family background" value={form.family} onChangeText={set('family')} placeholder="e.g. Joint family, business" />
            <Field label="About" value={form.about} onChangeText={set('about')} placeholder="A few lines about yourself" multiline maxLength={500} />
            <UploadBox label="Photos" hint="Up to 5 JPG or PNG, 2 MB each" />
            <UploadBox label="Biodata" hint="PDF, kept private until you accept a request" />
            <Notice
              title="Needs approval"
              body="Your city admin reviews the profile before other members can see it."
            />
            <Button title="Submit profile" disabled={!ready} onPress={() => setSent(true)} />
          </ScrollView>
        </>
      )}
    </SafeAreaView>
  );
}
