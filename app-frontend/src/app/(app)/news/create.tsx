import { Image } from 'expo-image';
import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Field, Notice, ScreenHeader, StatusView, UploadBox } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, mediaUrl, upload, type PickedFile } from '@/lib/api';
import { useT } from '@/lib/i18n';

// backend cityadmin/content/schema.py MediaOut / NewsSubmit
type Media = { media_key: string; media_url: string };
const MAX_EXTRA = 5;

export default function CreateNews() {
  const t = useT();
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [banner, setBanner] = useState<Media>();
  const [extras, setExtras] = useState<Media[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [sent, setSent] = useState(false);

  // UploadBox shows its own spinner; a failed upload lands in the error notice
  const send = (f: PickedFile) =>
    upload<Media>('/member/news/media', 'POST', f).then(
      (m) => (setError(undefined), m),
      (e) => (setError(e.message), undefined),
    );

  async function submit() {
    setBusy(true);
    setError(undefined);
    try {
      await api('/member/news', {
        method: 'POST',
        body: { title, body, media_key: banner!.media_key, extra_media_keys: extras.map((x) => x.media_key) },
      });
      setSent(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (sent)
    return (
      <SafeAreaView className="flex-1 bg-cream">
        <StatusView
          icon={{ ios: 'checkmark.seal.fill', android: 'verified', web: 'verified' }}
          title="News sent for approval"
          body="Your city admin will review it. Once approved, it shows up in the news feed for everyone."
          action="Back to news"
          onAction={() => router.back()}
        />
      </SafeAreaView>
    );

  return (
    <SafeAreaView className="flex-1 bg-cream">
      <ScreenHeader title="Create news" back />
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 20, paddingTop: 4, gap: 18 }}>
        <Field label="Title" value={title} onChangeText={setTitle} placeholder="What's the news?" maxLength={200} />
        {banner ? (
          <Thumb uri={banner.media_url} wide onRemove={() => setBanner(undefined)} />
        ) : (
          <UploadBox
            label="Banner image"
            hint="JPG or PNG, landscape works best"
            onPick={async (f) => setBanner(await send(f))}
          />
        )}
        <Field label="Content" value={body} onChangeText={setBody} placeholder="Write the full news here" multiline maxLength={10000} />
        {extras.length > 0 && (
          <View className="flex-row flex-wrap gap-3">
            {extras.map((x) => (
              <Thumb key={x.media_key} uri={x.media_url} onRemove={() => setExtras(extras.filter((e) => e !== x))} />
            ))}
          </View>
        )}
        {extras.length < MAX_EXTRA && (
          <UploadBox
            label="Extra images"
            hint={t('Add more photos · {n} left', { n: MAX_EXTRA - extras.length })}
            optional
            onPick={async (f) => {
              const m = await send(f);
              if (m) setExtras((xs) => [...xs, m]);
            }}
          />
        )}
        <Notice title="Needs approval" body="Your city admin reviews news before it is published." />
        {error && <Notice title="Something went wrong" body={error} tone={Palette.rejected} />}
        <Button
          title="Submit news"
          disabled={busy || !title.trim() || !body.trim() || !banner}
          onPress={submit}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function Thumb({ uri, wide, onRemove }: { uri: string; wide?: boolean; onRemove: () => void }) {
  const t = useT();
  return (
    <View>
      <Image
        source={{ uri: mediaUrl(uri)! }}
        contentFit="cover"
        style={wide ? { width: '100%', height: 160, borderRadius: 16 } : { width: 96, height: 96, borderRadius: 16 }}
      />
      <Pressable
        onPress={onRemove}
        accessibilityRole="button"
        accessibilityLabel={t('Remove photo')}
        hitSlop={8}
        className="absolute right-1 top-1 rounded-full bg-white p-1">
        <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={14} tintColor={Palette.ink} />
      </Pressable>
    </View>
  );
}
