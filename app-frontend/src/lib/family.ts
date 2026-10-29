import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { api } from '@/lib/api';

// backend member/family/schema.py HouseholdOut
export type Relative = {
  family_member_id: string;
  full_name: string;
  full_name_i18n: Record<string, string>;
  relationship: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  rejection_reason: string | null;
};
export type Household = {
  household_id: string;
  family_name: string;
  family_name_i18n: Record<string, string>;
  native_place: string | null;
  members: { member_id: string; full_name: string | null; full_name_i18n: Record<string, string>; is_household_head: boolean }[];
  relatives: Relative[];
};

/** Refetches on focus, so a relative added on the add-member screen shows up on return. */
export function useHousehold() {
  const [household, setHousehold] = useState<Household>();
  const [error, setError] = useState<string>();
  useFocusEffect(
    useCallback(() => {
      api<Household>('/member/family').then(setHousehold, (e) => setError(e.message));
    }, []),
  );
  return { household, error };
}
