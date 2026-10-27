import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Field, Notice, ScreenHeader, StatusView, UploadBox } from '@/components/ui/form';

export default function CreateNews() {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [sent, setSent] = useState(false);

  return (
    <SafeAreaView className="flex-1 bg-cream">
      {sent ? (
        <StatusView
          icon={{ ios: 'checkmark.seal.fill', android: 'verified', web: 'verified' }}
          title="News sent for approval"
          body="Your city admin will review it. Once approved, it shows up in the news feed for everyone."
          action="Back to news"
          onAction={() => router.back()}
        />
      ) : (
        <>
          <ScreenHeader title="Create news" back />
          {/* ponytail: submit only shows the sent state until the news API exists */}
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
            <Field label="Title" value={title} onChangeText={setTitle} placeholder="What's the news?" maxLength={200} />
            <UploadBox label="Banner image" hint="JPG or PNG, landscape works best" />
            <Field label="Content" value={body} onChangeText={setBody} placeholder="Write the full news here" multiline />
            <UploadBox label="Extra images" hint="Add more photos" optional />
            <Notice title="Needs approval" body="Your city admin reviews news before it is published." />
            <Button title="Submit news" disabled={!title.trim() || !body.trim()} onPress={() => setSent(true)} />
          </ScrollView>
        </>
      )}
    </SafeAreaView>
  );
}
