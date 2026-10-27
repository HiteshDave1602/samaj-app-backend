import { router } from 'expo-router';
import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import type { ReactNode } from 'react';
import { Pressable, Text, TextInput, View, type TextInputProps } from 'react-native';

import { Palette } from '@/constants/theme';

type Tone = { DEFAULT: string; container: string };

export const initials = (name: string) =>
  name.split(' ').map((w) => w[0]).slice(0, 2).join('');

export function ScreenHeader({ title, back, right }: { title: string; back?: boolean; right?: ReactNode }) {
  return (
    <View className="flex-row items-center gap-2 px-5 py-3">
      {back && (
        <Pressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel="Back"
          className="-ml-2 p-2">
          <SymbolView
            name={{ ios: 'chevron.left', android: 'arrow_back', web: 'arrow_back' }}
            size={22}
            tintColor={Palette.ink}
          />
        </Pressable>
      )}
      <Text className="flex-1 font-headline text-2xl text-brand">{title}</Text>
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
      <Text className={`font-inter-semibold ${small ? 'text-sm' : 'text-base'} ${text}`}>{title}</Text>
    </Pressable>
  );
}

export function Field({ label, hint, multiline, ...props }: TextInputProps & { label: string; hint?: string }) {
  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">{label}</Text>
      <TextInput
        {...props}
        multiline={multiline}
        placeholderTextColor={Palette.muted}
        textAlignVertical={multiline ? 'top' : 'center'}
        className={`rounded-2xl border border-line bg-white px-4 font-inter text-base text-ink ${multiline ? 'min-h-32 py-3' : 'h-12'}`}
      />
      {hint && <Text className="mt-1 font-inter text-xs text-muted">{hint}</Text>}
    </View>
  );
}

export function Chips<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly T[];
  value?: T;
  onChange: (v: T) => void;
}) {
  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">{label}</Text>
      <View className="flex-row flex-wrap gap-2">
        {options.map((o) => (
          <Pressable
            key={o}
            onPress={() => onChange(o)}
            accessibilityRole="radio"
            accessibilityState={{ selected: o === value }}
            className={`rounded-full border px-4 py-2 ${o === value ? 'border-primary bg-primary-container' : 'border-line bg-white'}`}>
            <Text className={`font-inter-medium text-sm ${o === value ? 'text-primary' : 'text-subtle'}`}>{o}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

// ponytail: tap does nothing until expo-image-picker / expo-document-picker are added
export function UploadBox({ label, hint, optional }: { label: string; hint: string; optional?: boolean }) {
  return (
    <View>
      <Text className="mb-1.5 font-inter-medium text-sm text-ink">
        {label}
        {optional && <Text className="text-muted"> (optional)</Text>}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Upload ${label}`}
        className="h-28 items-center justify-center rounded-2xl border border-dashed border-muted bg-surface active:opacity-80">
        <SymbolView
          name={{ ios: 'square.and.arrow.up', android: 'upload', web: 'upload' }}
          size={26}
          tintColor={Palette.primary.DEFAULT}
        />
        <Text className="mt-1 font-inter text-xs text-muted">{hint}</Text>
      </Pressable>
    </View>
  );
}

export function Notice({ title, body, tone = Palette.pending }: { title: string; body: string; tone?: Tone }) {
  return (
    <View className="rounded-2xl p-4" style={{ backgroundColor: tone.container }}>
      <Text className="font-inter-semibold text-sm" style={{ color: tone.DEFAULT }}>{title}</Text>
      <Text className="mt-0.5 font-inter text-sm" style={{ color: tone.DEFAULT }}>{body}</Text>
    </View>
  );
}

export function Avatar({ name, size = 56, tone = Palette.primary }: { name: string; size?: number; tone?: Tone }) {
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
  return (
    <View className="flex-1 px-6">
      <View className="flex-1 items-center justify-center">
        <View
          className="h-40 w-40 items-center justify-center rounded-full"
          style={{ backgroundColor: tone.container }}>
          <SymbolView name={icon} size={64} tintColor={tone.DEFAULT} />
        </View>
        <Text className="mt-8 text-center font-headline text-3xl text-brand">{title}</Text>
        <Text className="mt-2 text-center font-inter text-base leading-6 text-subtle">{body}</Text>
      </View>
      <View className="pb-6">
        <Button title={action} onPress={onAction} />
      </View>
    </View>
  );
}
