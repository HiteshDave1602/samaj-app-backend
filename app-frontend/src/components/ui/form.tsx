import DateTimePicker from '@react-native-community/datetimepicker';
import * as DocumentPicker from 'expo-document-picker';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { useState, type ReactNode } from 'react';
import { ActivityIndicator, Platform, Pressable, Text, TextInput, View, type TextInputProps } from 'react-native';

import { Palette } from '@/constants/theme';
import { mediaUrl, parseDmy, toDmy, type PickedFile } from '@/lib/api';
import { useT } from '@/lib/i18n';

type Tone = { DEFAULT: string; container: string };

export const initials = (name: string) =>
  name.split(' ').map((w) => w[0]).slice(0, 2).join('');

// Components below translate their own text props (lib/i18n.ts), so screens pass plain English.
export function ScreenHeader({ title, back, right }: { title: string; back?: boolean; right?: ReactNode }) {
  const t = useT();
  return (
    <View className="flex-row items-center gap-2 px-5 py-3">
      {back && (
        <Pressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel={t('Back')}
          className="-ml-2 p-2">
          <SymbolView
            name={{ ios: 'chevron.left', android: 'arrow_back', web: 'arrow_back' }}
            size={22}
            tintColor={Palette.ink}
          />
        </Pressable>
      )}
      <Text className="flex-1 font-headline text-2xl text-brand">{t(title)}</Text>
      {right}
    </View>
  );
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled,
  small,
}: {
  title: string;
  onPress?: () => void;
  variant?: 'primary' | 'outlined' | 'tonal';
  disabled?: boolean;
  small?: boolean;
}) {
  const t = useT();
  const box = {
    primary: 'bg-primary',
    outlined: 'border border-muted',
    tonal: 'bg-primary-container',
  }[variant];
  const text = variant === 'primary' ? 'text-white' : 'text-primary';
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      className={`items-center rounded-full ${small ? 'px-4 py-2' : 'py-4'} ${box} ${disabled ? 'opacity-40' : 'active:opacity-80'}`}>
      <Text className={`font-inter-semibold ${small ? 'text-sm' : 'text-base'} ${text}`}>{t(title)}</Text>
    </Pressable>
  );
}

export function Field({ label, hint, multiline, placeholder, ...props }: TextInputProps & { label: string; hint?: string }) {
  const t = useT();
  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">{t(label)}</Text>
      <TextInput
        {...props}
        placeholder={placeholder && t(placeholder)}
        multiline={multiline}
        placeholderTextColor={Palette.muted}
        textAlignVertical={multiline ? 'top' : 'center'}
        className={`rounded-2xl border border-line bg-white px-4 font-inter text-base text-ink ${multiline ? 'min-h-32 py-3' : 'h-12'}`}
      />
      {hint && <Text className="mt-1 font-inter text-xs text-muted">{t(hint)}</Text>}
    </View>
  );
}

/** '0507' -> '05/07': slashes go in as digits are typed. */
const slashDate = (v: string) => v.replace(/\D/g, '').slice(0, 8).replace(/^(\d{2})(\d)/, '$1/$2').replace(/^(\d{2}\/\d{2})(\d)/, '$1/$2');
/** A day over 31 or a month over 12 is wrong before the year is even typed. */
const badSoFar = (v: string) => {
  const [d, m] = v.split('/');
  return (d?.length === 2 && (+d < 1 || +d > 31)) || (m?.length === 2 && (+m < 1 || +m > 12));
};

/** Birth date as DD/MM/YYYY: typed, or picked from the phone's calendar. Impossible dates say so at once. */
export function DateField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [left, setLeft] = useState(false); // focus left the box: a half-typed date is wrong too
  const invalid = !!value && (value.length === 10 || left ? !parseDmy(value) : badSoFar(value));
  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">{t(label)}</Text>
      <View className={`h-12 flex-row items-center rounded-2xl border bg-white pl-4 ${invalid ? 'border-rejected' : 'border-line'}`}>
        <TextInput
          value={value}
          onChangeText={(v) => (onChange(slashDate(v)), setLeft(false))}
          onBlur={() => setLeft(true)}
          placeholder="DD/MM/YYYY"
          placeholderTextColor={Palette.muted}
          keyboardType="number-pad"
          maxLength={10}
          className="h-full flex-1 font-inter text-base text-ink"
        />
        {/* the native calendar has no web build; the web preview types the date */}
        {Platform.OS !== 'web' && (
          <Pressable
            onPress={() => setOpen(!open)}
            accessibilityRole="button"
            accessibilityLabel={t('Pick a date')}
            className="h-full w-12 items-center justify-center active:opacity-60">
            <SymbolView name={{ ios: 'calendar', android: 'calendar_month', web: 'calendar_month' }} size={22} tintColor={Palette.primary.DEFAULT} />
          </Pressable>
        )}
      </View>
      {invalid && <Text className="mt-1 font-inter text-xs text-rejected">{t('Not a valid date')}</Text>}
      {open && (
        <View>
          <DateTimePicker
            value={parseDmy(value) ?? new Date(1995, 0, 1)}
            mode="date"
            display={Platform.OS === 'ios' ? 'inline' : 'default'}
            minimumDate={new Date(1900, 0, 1)}
            maximumDate={new Date()}
            onChange={(e, d) => {
              if (Platform.OS !== 'ios') setOpen(false); // Android's dialog closes itself; iOS stays open until Done
              if (e.type === 'set' && d) onChange(toDmy(d));
            }}
          />
          {Platform.OS === 'ios' && <Button title="Done" variant="tonal" small onPress={() => setOpen(false)} />}
        </View>
      )}
    </View>
  );
}

export function Chips<T extends string>({
  label,
  options,
  value,
  onChange,
  display,
}: {
  label: string;
  options: readonly T[];
  value?: T;
  onChange: (v: T) => void;
  display?: (v: T) => string; // text for an option; default t(option)
}) {
  const t = useT();
  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">{t(label)}</Text>
      <View className="flex-row flex-wrap gap-2">
        {options.map((o) => (
          <Pressable
            key={o}
            onPress={() => onChange(o)}
            accessibilityRole="radio"
            accessibilityState={{ selected: o === value }}
            className={`rounded-full border px-4 py-2 ${o === value ? 'border-primary bg-primary-container' : 'border-line bg-white'}`}>
            <Text className={`font-inter-medium text-sm ${o === value ? 'text-primary' : 'text-subtle'}`}>{display ? display(o) : t(o)}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** Photos open the gallery; `pdf` also allows PDFs through the document picker. onPick does the upload. */
export function UploadBox({
  label,
  hint,
  optional,
  pdf,
  onPick,
}: {
  label: string;
  hint: string;
  optional?: boolean;
  pdf?: boolean;
  onPick: (file: PickedFile) => Promise<unknown>;
}) {
  const t = useT();
  const [busy, setBusy] = useState(false);

  async function pick() {
    let file: PickedFile | undefined;
    if (pdf) {
      const r = await DocumentPicker.getDocumentAsync({ type: ['image/jpeg', 'image/png', 'application/pdf'] });
      const a = r.assets?.[0];
      if (a) file = { uri: a.uri, name: a.name, mimeType: a.mimeType ?? 'application/octet-stream' };
    } else {
      const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
      const a = r.assets?.[0];
      if (a) file = { uri: a.uri, name: a.fileName ?? 'photo.jpg', mimeType: a.mimeType ?? 'image/jpeg' };
    }
    if (!file) return; // cancelled
    setBusy(true);
    await onPick(file).finally(() => setBusy(false));
  }

  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">
        {t(label)}
        {optional && <Text className="text-muted"> {t('(optional)')}</Text>}
      </Text>
      <Pressable
        onPress={pick}
        disabled={busy}
        accessibilityRole="button"
        accessibilityLabel={t('Upload {label}', { label: t(label) })}
        className="h-28 items-center justify-center rounded-2xl border border-dashed border-muted bg-surface active:opacity-80">
        {busy ? (
          <ActivityIndicator color={Palette.primary.DEFAULT} />
        ) : (
          <SymbolView
            name={{ ios: 'square.and.arrow.up', android: 'upload', web: 'upload' }}
            size={26}
            tintColor={Palette.primary.DEFAULT}
          />
        )}
        <Text className="mt-1 font-inter text-xs text-muted">{busy ? t('Uploading…') : t(hint)}</Text>
      </Pressable>
    </View>
  );
}

export function Notice({ title, body, tone = Palette.pending }: { title: string; body: string; tone?: Tone }) {
  const t = useT();
  return (
    <View className="rounded-2xl p-4" style={{ backgroundColor: tone.container }}>
      <Text className="font-inter-semibold text-sm" style={{ color: tone.DEFAULT }}>{t(title)}</Text>
      <Text className="mt-0.5 font-inter text-sm" style={{ color: tone.DEFAULT }}>{t(body)}</Text>
    </View>
  );
}

/** photo: an API media path (e.g. photo_url); falls back to initials when absent. */
export function Avatar({ name, size = 56, tone = Palette.primary, photo }: { name: string; size?: number; tone?: Tone; photo?: string | null }) {
  const uri = mediaUrl(photo ?? null);
  if (uri) return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2 }} accessibilityLabel={name} />;
  return (
    <View
      className="items-center justify-center rounded-full"
      style={{ width: size, height: size, backgroundColor: tone.container }}>
      <Text className="font-inter-semibold" style={{ color: tone.DEFAULT, fontSize: size * 0.34 }}>
        {initials(name)}
      </Text>
    </View>
  );
}

export function StatusView({
  icon,
  tone = Palette.primary,
  title,
  body,
  action,
  onAction,
}: {
  icon: SymbolViewProps['name'];
  tone?: Tone;
  title: string;
  body: string;
  action: string;
  onAction: () => void;
}) {
  const t = useT();
  return (
    <View className="flex-1 px-6">
      <View className="flex-1 items-center justify-center">
        <View
          className="h-40 w-40 items-center justify-center rounded-full"
          style={{ backgroundColor: tone.container }}>
          <SymbolView name={icon} size={64} tintColor={tone.DEFAULT} />
        </View>
        <Text className="mt-8 text-center font-headline text-3xl text-brand">{t(title)}</Text>
        <Text className="mt-2 text-center font-inter text-base leading-6 text-subtle">{t(body)}</Text>
      </View>
      <View className="pb-6">
        <Button title={t(action)} onPress={onAction} />
      </View>
    </View>
  );
}
