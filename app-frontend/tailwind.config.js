/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  // 'media' crashes NativeWind's web runtime; 'class' still follows the system scheme until set manually
  darkMode: 'class',
  theme: {
    extend: {
      colors: require('./src/constants/palette'),
      // RN needs one family per weight; names match the keys loaded by useFonts in src/app/_layout.tsx
      fontFamily: {
        headline: ['BalooBhai2_700Bold'],
        inter: ['Inter_400Regular'],
        'inter-medium': ['Inter_500Medium'],
        'inter-semibold': ['Inter_600SemiBold'],
      },
    },
  },
  plugins: [],
};
