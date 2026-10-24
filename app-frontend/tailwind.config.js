/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  // 'media' crashes NativeWind's web runtime; 'class' still follows the system scheme until set manually
  darkMode: 'class',
  theme: { extend: {} },
  plugins: [],
};
