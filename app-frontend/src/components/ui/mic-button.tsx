import { requireOptionalNativeModule } from 'expo';
import { SymbolView } from 'expo-symbols';
import { type RefObject, useState } from 'react';
import { Alert, Pressable } from 'react-native';

import { useT } from '@/lib/i18n';
import { usePalette } from '@/lib/theme';

// Expo Go has no speech module and importing the library there crashes the whole app, so load it only when present.
const speech: typeof import('expo-speech-recognition') | null = requireOptionalNativeModule('ExpoSpeechRecognition')
  ? // eslint-disable-next-line @typescript-eslint/no-require-imports -- a static import would crash Expo Go
    require('expo-speech-recognition')
  : null;

/**
 * Mic toggle that streams what the user says into onText, live while they speak.
 * Where speech isn't built in (Expo Go), tapping focuses `input` so the keyboard's own dictation mic fills it instead.
 */
export function MicButton({ input, ...props }: { onText: (text: string) => void; input?: RefObject<{ focus(): void } | null> }) {
  return speech ? <Mic {...props} speech={speech} /> : <KeyboardDictation input={input} />;
}

function KeyboardDictation({ input }: { input?: RefObject<{ focus(): void } | null> }) {
  const palette = usePalette();
  const t = useT();
  return (
    <Pressable
      onPress={() => {
        input?.current?.focus();
        Alert.alert(t('Voice search'), t('Tap the mic on your keyboard and speak the name'));
      }}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={t('Voice search')}>
      <SymbolView name={{ ios: 'mic', android: 'mic', web: 'mic' }} size={20} tintColor={palette.muted} />
    </Pressable>
  );
}

function Mic({ onText, speech }: { onText: (text: string) => void; speech: typeof import('expo-speech-recognition') }) {
  const palette = usePalette();
  const { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } = speech;
  const t = useT();
  const [listening, setListening] = useState(false);

  // ponytail: events are app-wide, so two MicButtons on one screen would both fill; track an owner id if that happens
  useSpeechRecognitionEvent('start', () => setListening(true));
  useSpeechRecognitionEvent('end', () => setListening(false));
  useSpeechRecognitionEvent('result', (e) => onText(e.results[0]?.transcript ?? ''));
  useSpeechRecognitionEvent('error', (e) => {
    setListening(false);
    if (e.error !== 'aborted') Alert.alert(t('Could not hear you, please try again'));
  });

  async function toggle() {
    if (listening) return ExpoSpeechRecognitionModule.stop();
    const { granted } = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!granted) return Alert.alert(t('Allow microphone access to search by voice'));
    // en-IN whatever the app language: the server matches names in English only, Gujarati script would never match
    ExpoSpeechRecognitionModule.start({ lang: 'en-IN', interimResults: true, continuous: false });
  }

  return (
    <Pressable
      onPress={toggle}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={t(listening ? 'Stop listening' : 'Voice search')}
      accessibilityState={{ selected: listening }}>
      <SymbolView
        name={{ ios: listening ? 'mic.fill' : 'mic', android: 'mic', web: 'mic' }}
        size={20}
        tintColor={listening ? palette.primary.DEFAULT : palette.muted}
      />
    </Pressable>
  );
}
