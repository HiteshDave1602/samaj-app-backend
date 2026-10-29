import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';

import { restoreSession } from '@/lib/api';

// A stored refresh token skips onboarding; null until we know (the splash overlay is still up).
export default function Index() {
  const [signedIn, setSignedIn] = useState<boolean>();
  useEffect(() => {
    restoreSession().then((s) => setSignedIn(!!s));
  }, []);
  if (signedIn === undefined) return null;
  return <Redirect href={signedIn ? '/home' : '/onboarding'} />;
}
