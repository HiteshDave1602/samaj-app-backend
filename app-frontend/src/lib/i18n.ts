import { useSyncExternalStore } from 'react';

import { gu, hi } from '@/constants/translations';
import { api, memberStatus, store } from '@/lib/api';

export const LANGUAGES = { en: 'English', gu: 'ગુજરાતી', hi: 'हिन्दी' } as const;
export type Lang = keyof typeof LANGUAGES;

const DICTS: Record<Lang, Record<string, string>> = { en: {}, gu, hi };
let lang: Lang = 'en';
const listeners = new Set<() => void>();

/** The English text is the key; a missing translation falls back to it. `{name}` placeholders come from vars. */
export function t(en: string, vars?: Record<string, string | number>) {
  const s = DICTS[lang][en] ?? en;
  return vars ? s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k])) : s;
}

export const getLang = () => lang;
/** For toLocaleDateString. */
export const locale = () => `${lang}-IN`;

/** Names and places from the API come with *_i18n spellings ({gu, hi}); this picks the current one, else the original. */
export const loc = (en: string | null, i18n?: Record<string, string> | null) => i18n?.[lang] || en;

/** Panchang, rashi and gotra text is English words ('Kartika Shukla Navami'), each looked up on its own. kind picks
 * the meaning of a word shared between lists: Shravana the month vs the nakshatra. Pass the t from useT(). */
export function tWords(tr: typeof t, s: string, kind?: 'nakshatra' | 'yoga') {
  return s
    .split(' ')
    .map((w) => {
      const own = kind && tr(`${w} (${kind})`);
      return own && own !== `${w} (${kind})` ? own : tr(w);
    })
    .join(' ');
}

/** Backend enums are UPPER_SNAKE; 'SON_IN_LAW' -> 'Son in law', then translated. */
export const label = (v: string) => t(v.charAt(0) + v.slice(1).toLowerCase().replace(/_/g, ' '));

/** Call once before the first render (the root layout does). */
export async function loadLang() {
  const saved = await store.get('lang').catch(() => null);
  if (saved && saved in DICTS) lang = saved as Lang;
}

/** Saved on the device; mirrored to the server when logged in, so notifications can use it too. */
export function setLang(l: Lang) {
  lang = l;
  store.set('lang', l).catch(() => {});
  listeners.forEach((f) => f());
  syncLang();
}

export function syncLang() {
  if (memberStatus()) api('/member/me', { method: 'PUT', body: { language: lang } }).catch(() => {});
}

const subscribe = (f: () => void) => (listeners.add(f), () => listeners.delete(f));

// One t per language: the React Compiler caches text by t's identity, so it must change when the language does.
const T_BY_LANG = Object.fromEntries(
  (Object.keys(DICTS) as Lang[]).map((l) => [l, (en: string, vars?: Record<string, string | number>) => t(en, vars)]),
) as Record<Lang, typeof t>;

/** The current language, re-rendering on change (getLang() alone is cached by the React Compiler). */
export function useLang() {
  return useSyncExternalStore(subscribe, getLang, getLang);
}

/** Every component that shows text calls this, so it re-renders when the language changes. */
export function useT() {
  return T_BY_LANG[useLang()];
}
