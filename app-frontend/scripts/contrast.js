// node scripts/contrast.js — WCAG contrast of the text/background pairs the screens use, for both themes.
// Fails if dark has a pair under AA (4.5) or the two themes' keys drift apart. Light is design-owned:
// its known misses (accent as text, muted on surface) are only reported.
const { light, dark } = require('../src/constants/palette');

const keys = (o, p = '') => Object.entries(o).flatMap(([k, v]) => (typeof v === 'object' ? keys(v, `${p}${k}.`) : [p + k]));
const lum = (hex) => {
  const c = hex.slice(1).match(/../g).map((h) => parseInt(h, 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
const get = (p, k) => k.split('.').reduce((o, s) => o[s], p);
const PAIRS = [
  ['ink', 'cream'], ['ink', 'card'], ['ink', 'surface'], ['subtle', 'cream'], ['subtle', 'card'],
  ['muted', 'cream'], ['muted', 'card'], ['muted', 'surface'],
  ['primary.DEFAULT', 'cream'], ['primary.DEFAULT', 'card'], ['primary.DEFAULT', 'primary.container'], ['on-primary', 'primary.DEFAULT'],
  ['secondary.DEFAULT', 'cream'], ['secondary.DEFAULT', 'card'], ['secondary.DEFAULT', 'secondary.container'], ['on-secondary', 'secondary.DEFAULT'],
  ['accent.DEFAULT', 'cream'], ['accent.DEFAULT', 'accent.container'], ['on-accent', 'accent.DEFAULT'], ['ink', 'accent.container'],
  ['brand.DEFAULT', 'cream'], ['brand.DEFAULT', 'card'], ['brand.DEFAULT', 'brand.container'],
  ['approved.DEFAULT', 'approved.container'], ['pending.DEFAULT', 'pending.container'],
  ['rejected.DEFAULT', 'rejected.container'], ['rejected.DEFAULT', 'cream'], ['info.DEFAULT', 'info.container'],
];

const drift = keys(light).join() !== keys(dark).join();
if (drift) console.error('light and dark palettes have different keys');
let failed = drift;
for (const [mode, p] of Object.entries({ light, dark })) {
  const low = PAIRS.filter(([f, b]) => ratio(get(p, f), get(p, b)) < 4.5).map(([f, b]) => `${f} on ${b} (${ratio(get(p, f), get(p, b)).toFixed(2)})`);
  console.log(`${mode}: ${low.length ? `under 4.5: ${low.join(', ')}` : 'all pairs AA'}`);
  if (mode === 'dark' && low.length) failed = true;
}
process.exit(failed ? 1 : 0);
