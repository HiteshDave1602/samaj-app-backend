import { Image } from 'expo-image';
import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useEffect, useState } from 'react';
import { Keyboard, Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { Palette } from '@/constants/theme';
import { useT } from '@/lib/i18n';

const SPONSOR_URL = 'https://www.instagram.com/shastribhavinofficial/';
const DEVELOPER_URL = 'https://www.vrattiks.io/';
const LOGO_RATIO = 600 / 587; // height / width of assets/images/brand/logo.png
// header height, logo width, logo top margin
const SIZES = { full: [330, 168, 48], compact: [190, 112, 36], mini: [104, 64, 20] } as const;

/** True while the on-screen keyboard is up. */
export function useKeyboardOpen() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    // iOS announces the keyboard before it moves; Android only after
    const ios = Platform.OS === 'ios';
    const subs = [
      Keyboard.addListener(ios ? 'keyboardWillShow' : 'keyboardDidShow', () => setOpen(true)),
      Keyboard.addListener(ios ? 'keyboardWillHide' : 'keyboardDidHide', () => setOpen(false)),
    ];
    return () => subs.forEach((s) => s.remove());
  }, []);
  return open;
}

/** Login and registration header: the Pragati Mandal logo on the Kul Sangam cover's sky and crowd.
 * mini: while the keyboard is up, so the form above it stays in view. */
export function BrandHeader({ size = 'full', back }: { size?: keyof typeof SIZES; back?: boolean }) {
  const t = useT();
  const [height, logo, top] = SIZES[size];
  return (
    <View style={{ height }}>
      <Image source={require('@/assets/images/brand/hero.jpg')} style={StyleSheet.absoluteFill} contentFit="cover" contentPosition="bottom" />
      <Image
        source={require('@/assets/images/brand/logo.png')}
        style={{ width: logo, height: logo * LOGO_RATIO, alignSelf: 'center', marginTop: top }}
        contentFit="contain"
        accessibilityLabel="Pragati Mandal"
      />
      {back && (
        <Pressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel={t('Back')}
          className="absolute left-4 top-3 h-10 w-10 items-center justify-center rounded-full bg-white/85">
          <SymbolView name={{ ios: 'chevron.left', android: 'arrow_back', web: 'arrow_back' }} size={20} tintColor={Palette.brand.DEFAULT} />
        </Pressable>
      )}
    </View>
  );
}

/** "Sponsored by Bhavin Shastri / Developed by Vrattiks Intelligence LLP"; each name opens their page. */
export function Credits() {
  const t = useT();
  const line = (template: string, name: string, url: string) => {
    const [before, after] = t(template, { name: '\u0000' }).split('\u0000'); // the name sits where the translation puts it
    return (
      <Text className="text-center font-inter-medium text-xs leading-5 text-muted">
        {before}
        <Text onPress={() => Linking.openURL(url)} accessibilityRole="link" className="font-inter-semibold text-ink underline">
          {name}
        </Text>
        {after}
      </Text>
    );
  };
  return (
    <View className="mt-auto border-t border-line pb-2 pt-4">
      {line('Sponsored by {name}', 'Bhavin Shastri', SPONSOR_URL)}
      {line('Developed by {name}', 'Vrattiks Intelligence LLP', DEVELOPER_URL)}
    </View>
  );
}
