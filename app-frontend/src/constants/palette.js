// Pragati Samaj design tokens v2 (docs/Colour & type — blue primary.pdf).
// Shared by tailwind.config.js and src/constants/theme.ts.
module.exports = {
  primary: { DEFAULT: '#00739F', container: '#E0F2FE' }, // buttons, links, active nav, focus
  secondary: { DEFAULT: '#8E2466', container: '#FCE7F3' }, // matrimony, secondary actions, tags
  accent: { DEFAULT: '#F08000', container: '#FFF1DE' }, // badges, highlights, Panchang
  brand: { DEFAULT: '#2E3192', container: '#E6E7F7' }, // brand name, display headings
  cream: '#FFFBF5',
  surface: '#F6F0EA',
  line: '#EADFD6',
  muted: '#7A6E86',
  subtle: '#5B5068',
  ink: '#1C1530',
  // ponytail: status hexes eyeballed from the PDF chips, swap for exact values if design shares them
  approved: { DEFAULT: '#166534', container: '#DCFCE7' },
  pending: { DEFAULT: '#92400E', container: '#FEF3C7' },
  rejected: { DEFAULT: '#991B1B', container: '#FEE2E2' },
  info: { DEFAULT: '#075985', container: '#E0F2FE' },
};
