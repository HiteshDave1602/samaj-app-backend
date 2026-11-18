const { light, dark } = require('./src/constants/palette');

// Each palette colour is a CSS variable of "r g b" channels (so opacity modifiers like shadow-ink/10 still work):
// :root holds light, .dark:root holds dark, and NativeWind swaps them with the colour scheme (src/lib/theme.ts).
const name = (key, shade) => (shade === 'DEFAULT' ? key : `${key}-${shade}`);
const entries = (p) =>
  Object.entries(p).flatMap(([k, v]) => (typeof v === 'string' ? [[k, v]] : Object.entries(v).map(([s, c]) => [name(k, s), c])));
const vars = (p) =>
  Object.fromEntries(entries(p).map(([k, hex]) => [`--${k}`, hex.slice(1).match(/../g).map((h) => parseInt(h, 16)).join(' ')]));
const ref = (k) => `rgb(var(--${k}) / <alpha-value>)`;
const colors = Object.fromEntries(
  Object.entries(light).map(([k, v]) => [
    k,
    typeof v === 'string' ? ref(k) : Object.fromEntries(Object.keys(v).map((s) => [s, ref(name(k, s))])),
  ]),
);

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  // 'media' crashes NativeWind's web runtime; 'class' still follows the system scheme until set manually
  darkMode: 'class',
  theme: {
    extend: {
      colors,
      // RN needs one family per weight; names match the keys loaded by useFonts in src/app/_layout.tsx
      fontFamily: {
        headline: ['BalooBhai2_700Bold'],
        inter: ['Inter_400Regular'],
        'inter-medium': ['Inter_500Medium'],
        'inter-semibold': ['Inter_600SemiBold'],
      },
    },
  },
  plugins: [({ addBase }) => addBase({ ':root': vars(light), '.dark:root': vars(dark) })],
};
