import { Image } from 'expo-image';
import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Chips, DateField, Field, Notice, Problem, ScreenHeader, StatusView, UploadBox } from '@/components/ui/form';
import { api, mediaUrl, parseDmy, toDmy, upload, type PickedFile } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';
import { rules } from '@/lib/validate';

// backend cityadmin/content/schema.py MediaOut / NewsSubmit
type Media = { media_key: string; media_url: string };
const MAX_EXTRA = 5;
const DEFAULT_DAYS = 30; // backend MEMBER_NEWS_DAYS

export default function CreateNews() {
  const palette = usePalette();
  const t = useT();
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [banner, setBanner] = useState<Media>();
  const [extras, setExtras] = useState<Media[]>([]);
  const [kind, setKind] = useState<'News' | 'Ad'>('News');
  const [from, setFrom] = useState(() => toDmy(new Date()));
  const [until, setUntil] = useState(() => toDmy(new Date(Date.now() + DEFAULT_DAYS * 864e5)));
  const start = parseDmy(from, true);
  const end = parseDmy(until, true);
  const badRange = !!start && !!end && end < start;
  const titleError = rules.text(title, { required: true, max: 200 });
  const bodyError = rules.text(body, { required: true, max: 10000, multiline: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false);

  // UploadBox shows its own spinner; a failed upload lands in the error notice
  const send = (f: PickedFile) =>
    upload<Media>('/member/news/media', 'POST', f).then(
      (m) => (setError(undefined), m),
      (e) => (setError(e), undefined),
    );

  async function submit() {
    setBusy(true);
    setError(undefined);
    try {
      await api('/member/news', {
        method: 'POST',
        body: {
          title,
          body,
          media_key: banner!.media_key,
          extra_media_keys: extras.map((x) => x.media_key),
          as_ad: kind === 'Ad',
          // whole days in the phone's timezone: from the start of the first day to the end of the last
          start_at: start!.toISOString(),
          end_at: new Date(end!.getFullYear(), end!.getMonth(), end!.getDate() + 1).toISOString(),
        },
      });
      setSent(true);
    } catch (e) {
      setError(e);
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
        <Chips label="Show as" options={['News', 'Ad'] as const} value={kind} onChange={setKind} />
        <Field label="Title" value={title} onChangeText={setTitle} placeholder="What's the news?" maxLength={200} error={titleError} />
        {banner ? (
          <Thumb uri={banner.media_url} wide onRemove={() => setBanner(undefined)} />
        ) : (
          <UploadBox
            label="Banner image"
            hint="JPG or PNG, landscape works best"
            onPick={async (f) => setBanner(await send(f))}
          />
        )}
        <Field label="Content" value={body} onChangeText={setBody} placeholder="Write the full news here" multiline maxLength={10000} error={bodyError} />
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
        <View className="flex-row gap-3">
          <View className="flex-1">
            <DateField label="Active from" value={from} onChange={setFrom} future />
          </View>
          <View className="flex-1">
            <DateField label="Active until" value={until} onChange={setUntil} future />
          </View>
        </View>
        {badRange && <Notice title="Check the dates" body="The end date can't be before the start date." tone={palette.rejected} />}
        <Notice
          title="Needs approval"
          body={
            kind === 'Ad'
              ? 'Your city admin reviews ads before they are published. Ads show as sponsored cards with a View ad button.'
              : 'Your city admin reviews news before it is published.'
          }
        />
        <Problem title="Something went wrong" error={error} />
        <Button
          title={kind === 'Ad' ? 'Submit ad' : 'Submit news'}
          disabled={busy || !!titleError || !!bodyError || !banner || !start || !end || badRange}
          onPress={submit}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function Thumb({ uri, wide, onRemove }: { uri: string; wide?: boolean; onRemove: () => void }) {
  const palette = usePalette();
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
        className="absolute right-1 top-1 rounded-full bg-card p-1">
        <SymbolView name={{ ios: 'xmark', android: 'close', web: 'close' }} size={14} tintColor={palette.ink} />
      </Pressable>
    </View>
  );
}
