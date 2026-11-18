/**
 * Learn more about light and dark modes:
 * https://docs.expo.dev/guides/color-schemes/
 */

import { Colors } from '@/constants/theme';
import { useScheme } from '@/lib/theme';

export function useTheme() {
  return Colors[useScheme()];
}
