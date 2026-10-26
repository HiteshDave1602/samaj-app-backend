import { Redirect } from 'expo-router';

// ponytail: always onboards; once auth lands, signed-in users should skip straight to /home
export default function Index() {
  return <Redirect href="/onboarding" />;
}
