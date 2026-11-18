import { colorScheme } from 'nativewind';
import { useSyncExternalStore } from 'react';
import { Appearance, Platform, useColorScheme } from 'react-native';

import { Palettes } from '@/constants/theme';
import { store } from '@/lib/api';

export const THEMES = { system: 'System default', light: 'Light', dark: 'Dark' } as const;
export type ThemePref = keyof typeof THEMES;
export type Scheme = 'light' | 'dark';

let pref: ThemePref = 'system';
const listeners = new Set<() => void>();
const subscribe = (f: () => void) => (listeners.add(f), () => listeners.delete(f));
const getPref = () => pref;

/** Native: NativeWind passes this to Appearance.setColorScheme, so a pick also themes native views (date picker,
 * alerts, keyboard) and 'system' hands control back to the OS. Web: NativeWind only toggles the html .dark class,
 * so it gets the scheme 'system' means right now. */
function apply() {
  const os = Appearance.getColorScheme() === 'dark' ? 'dark' : 'light';
  colorScheme.set(Platform.OS === 'web' && pref === 'system' ? os : pref);
}
// native follows the OS by itself; web's 'system' has to be re-applied when the OS flips
if (Platform.OS === 'web') Appearance.addChangeListener(() => pref === 'system' && apply());

/** Call once before the first render (the root layout does), so the saved theme shows from the first frame. */
export async function loadTheme() {
  const saved = await store.get('theme').catch(() => null);
  if (saved && saved in THEMES) pref = saved as ThemePref;
  apply();
}

/** Saved on the device only; the OS changing its own scheme never overwrites it. */
export function setThemePref(p: ThemePref) {
  pref = p;
  store.set('theme', p).catch(() => {});
  apply();
  listeners.forEach((f) => f());
}

/** The saved choice: 'system', 'light' or 'dark'. */
export function useThemePref() {
  return useSyncExternalStore(subscribe, getPref, getPref);
}

/** The scheme on screen. Native's useColorScheme already includes a manual pick; web's only knows the OS. */
export function useScheme(): Scheme {
  const p = useThemePref();
  const system = useColorScheme();
  return p === 'system' ? (system === 'dark' ? 'dark' : 'light') : p;
}

/** Palette colours for JS props (tintColor, placeholderTextColor, tones). Classes like text-ink flip by themselves.
 * One object per scheme, so the React Compiler re-renders anything built from it when the theme changes. */
export function usePalette() {
  return Palettes[useScheme()];
}
