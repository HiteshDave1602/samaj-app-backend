// Pragati Samaj design tokens v2 (docs/Colour & type — blue primary.pdf), light and dark.
// The single source of colour: tailwind.config.js turns each key into a CSS variable (bg-cream, text-ink…)
// that flips with the theme, and usePalette() (src/lib/theme.ts) hands the same values to JS props.
// Both modes must have the same keys.
const light = {
  primary: { DEFAULT: '#00739F', container: '#E0F2FE' }, // buttons, links, active nav, focus
  secondary: { DEFAULT: '#8E2466', container: '#FCE7F3' }, // matrimony, secondary actions, tags
  accent: { DEFAULT: '#F08000', container: '#FFF1DE' }, // badges, highlights, Panchang
  brand: { DEFAULT: '#2E3192', container: '#E6E7F7' }, // brand name, display headings
  // text and icons sitting on a primary / secondary / accent fill
  'on-primary': '#FFFFFF',
  'on-secondary': '#FFFFFF',
  'on-accent': '#1C1530',
  cream: '#FFFBF5', // screen background
  surface: '#F6F0EA', // recessed areas: upload boxes
  card: '#FFFFFF', // cards, inputs, tab bar
  line: '#EADFD6', // borders, dividers
  muted: '#7A6E86', // hints, placeholders, idle icons
  subtle: '#5B5068', // secondary text
  ink: '#1C1530', // body text
  // ponytail: status hexes eyeballed from the PDF chips, swap for exact values if design shares them
  approved: { DEFAULT: '#166534', container: '#DCFCE7' },
  pending: { DEFAULT: '#92400E', container: '#FEF3C7' },
  rejected: { DEFAULT: '#991B1B', container: '#FEE2E2' },
  info: { DEFAULT: '#075985', container: '#E0F2FE' },
};

// Not an inversion: plum-tinted surfaces from ink's hue, brand colours lifted so they read as text on them,
// and the on-* colours go dark where a lifted fill got too light for white. Checked by scripts/contrast.js.
// ponytail: dark hexes derived here, not by design; swap in design's values when they exist.
const dark = {
  primary: { DEFAULT: '#4CB0E0', container: '#0B2A3A' },
  secondary: { DEFAULT: '#EC8BC4', container: '#3A1530' },
  accent: { DEFAULT: '#F59A2E', container: '#352211' },
  brand: { DEFAULT: '#AEB0F5', container: '#25264A' },
  'on-primary': '#00202F',
  'on-secondary': '#3A0A28',
  'on-accent': '#1C1530',
  cream: '#14111B',
  surface: '#1B1724',
  card: '#221D2C',
  line: '#383142',
  muted: '#A49AB1',
  subtle: '#C9C0D4',
  ink: '#F3EFF8',
  approved: { DEFAULT: '#86EFAC', container: '#0F2E1C' },
  pending: { DEFAULT: '#FCD34D', container: '#33240A' },
  rejected: { DEFAULT: '#FCA5A5', container: '#3D1616' },
  info: { DEFAULT: '#7DD3FC', container: '#0B2A3B' },
};

module.exports = { light, dark };
