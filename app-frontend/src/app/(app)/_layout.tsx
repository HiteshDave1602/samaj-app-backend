import { Redirect, Stack } from 'expo-router';

import { memberStatus } from '@/lib/api';

// Everything in (app) needs City Admin approval; anyone else waits on /pending.
// ponytail: the backend still serves feed and panchang to PENDING members (FR-08); this gate is app-side only.
export default function AppLayout() {
  if (memberStatus() !== 'ACTIVE') return <Redirect href="/pending" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
