import { Image } from 'expo-image';
import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { Avatar } from '@/components/ui/form';
import { Palette } from '@/constants/theme';
import { api, authedImage } from '@/lib/api';
import { label, loc, t } from '@/lib/i18n';

// Helpers below translate with the current language; their callers re-render via useT().
// backend member/matrimony/schema.py ProfileCard. The biodata stays private until a request is accepted.
export type ProfileCard = {
  profile_id: string;
  full_name: string | null;
  full_name_i18n: Record<string, string>;
  gender: string | null;
  age: number | null;
  education_level: string;
  education_detail: string | null;
  occupation: string | null;
  gotra: string | null;
  height_cm: number | null;
  native_place: string | null;
  native_place_i18n: Record<string, string>;
  family_background: string;
  location_city_name: string;
  location_city_name_i18n: Record<string, string>;
  managed_by: string;
  about: string | null;
  cover_photo_url: string | null;
};
export type BiodataRequest = {
  request_id: string;
  status: 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'WITHDRAWN';
  sent_by_me: boolean;
  counterpart_profile_id: string;
  counterpart: ProfileCard | null;
};

/** '26 yrs · Surat' */
export const summary = (p: ProfileCard) =>
  [p.age && t('{n} yrs', { n: p.age }), loc(p.location_city_name, p.location_city_name_i18n)].filter(Boolean).join(' · ');
export const education = (p: ProfileCard) => [label(p.education_level), p.education_detail].filter(Boolean).join(' · ');
/** 168 -> `5'6" (168 cm)` */
export const height = (cm: number) => {
  const inches = Math.round(cm / 2.54);
  return `${Math.floor(inches / 12)}'${inches % 12}" (${cm} cm)`;
};
export const title = (p: ProfileCard) =>
  loc(p.full_name, p.full_name_i18n) ?? (p.gender ? t('{gender} profile', { gender: label(p.gender) }) : t('Profile'));

export function Cover({ p, size }: { p: ProfileCard; size: number }) {
  return p.cover_photo_url ? (
    <Image source={authedImage(p.cover_photo_url)} style={{ width: size, height: size, borderRadius: size / 2 }} />
  ) : (
    <Avatar name={title(p)} size={size} tone={Palette.secondary} />
  );
}

/** Requests others sent to my profile, still awaiting my answer. Refetches on focus. */
export function useReceivedRequests() {
  const [requests, setRequests] = useState<BiodataRequest[]>([]);
  const load = useCallback(() => {
    // 403 until I'm active / 404-ish errors without a profile: just show no requests
    api<{ items: BiodataRequest[] }>('/member/matrimony/biodata-requests?box=received&status=PENDING').then(
      (r) => setRequests(r.items),
      () => setRequests([]),
    );
  }, []);
  useFocusEffect(load);
  return { requests, reload: load };
}
