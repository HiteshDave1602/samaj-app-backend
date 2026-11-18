import { requireOptionalNativeModule } from 'expo';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { Alert, Pressable, View } from 'react-native';

import { Palette } from '@/constants/theme';
import { useT } from '@/lib/i18n';

// Expo Go has no speech module and importing the library there crashes the whole app, so load it only when present.
const speech: typeof import('expo-speech-recognition') | null = requireOptionalNativeModule('ExpoSpeechRecognition')
  ? // eslint-disable-next-line @typescript-eslint/no-require-imports -- a static import would crash Expo Go
    require('expo-speech-recognition')
  : null;

/** Mic toggle that streams what the user says into onText, live while they speak. Greyed out where speech isn't built in (Expo Go). */
export function MicButton(props: { onText: (text: string) => void }) {
  return speech ? <Mic {...props} speech={speech} /> : <MicUnavailable />;
}

function MicUnavailable() {
  const t = useT();
  return (
    <View
      accessible
      accessibilityLabel={t('Voice search')}
      accessibilityState={{ disabled: true }}
      style={{ opacity: 0.4 }}>
      <SymbolView name={{ ios: 'mic.slash', android: 'mic_off', web: 'mic_off' }} size={20} tintColor={Palette.muted} />
    </View>
  );
}

function Mic({ onText, speech }: { onText: (text: string) => void; speech: typeof import('expo-speech-recognition') }) {
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
        tintColor={listening ? Palette.primary.DEFAULT : Palette.muted}
      />
    </Pressable>
  );
}
