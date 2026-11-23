// Instant feedback that mirrors backend/core/validation.py (and web-frontend/src/shared/validate.js; keep them in step).
// The server re-checks everything: this only saves a round trip. docs/input-validation-rules.md lists the rules.
// Each rule takes the raw value and returns '' when fine, else an English message (Field translates it).

const BIDI = /[‪-‮⁦-⁩]/g; // display-order overrides, used to disguise text
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;
const RUN4 = /(.)\1{3}/u;
const KEYBOARD = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm', 'abcdefghijklmnopqrstuvwxyz', '1234567890'];
const PLACEHOLDERS = new Set(['test', 'testing', 'tester', 'asdf', 'qwerty', 'dummy', 'sample', 'fake', 'name', 'fullname',
  'firstname', 'lastname', 'na', 'none', 'null', 'undefined', 'unknown', 'abc', 'xyz', 'xxx', 'noname']);
// ZWNJ/ZWJ (U+200C/D) shape Gujarati and Hindi conjuncts, so names may contain them
const NAME_CHARS = /^[\p{L}\p{M}‌‍ .'’()-]+$/u;
const EMAIL = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$/;

/** NFC, no control characters, trimmed; one line: single spaces; multiline: tidy lines, one blank line at most. */
export function clean(v: string, multiline = false): string {
  const s = (v ?? '').normalize('NFC').replace(BIDI, '').replace(/\r\n?/g, '\n').replace(CONTROL, '');
  if (!multiline) return s.split(/\s+/).filter(Boolean).join(' ');
  return s.split('\n').map((l) => l.replace(/[^\S\n]+/g, ' ').trim()).join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

const letters = (v: string) => (v.match(/\p{L}/gu) ?? []).join('');
const mash = (w: string) =>
  w.length >= 4 && KEYBOARD.some((r) => r.includes(w.toLowerCase()) || [...r].reverse().join('').includes(w.toLowerCase()));

type Opts = { required?: boolean; max?: number; multiline?: boolean };
type Rule = (v: string, o?: Opts) => string;

/** Shared front of every text rule: empty / too long, then the field's own check on the cleaned value. */
const text = (check: (v: string) => string): Rule => (raw, { required = false, max = 120, multiline = false } = {}) => {
  const v = clean(raw, multiline);
  if (!v) return required ? 'Required' : '';
  if (v.length > max) return `Keep it to ${max} characters`;
  return check(v);
};

// must match MaritalStatus / BloodGroup in backend member/auth/schema.py
export const MARITAL = ['Single', 'Married', 'Widowed', 'Divorced'] as const;
export const BLOOD = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] as const;
export type Marital = (typeof MARITAL)[number];
export type Blood = (typeof BLOOD)[number];

export const rules = {
  personName: text((v) => {
    if (!NAME_CHARS.test(v)) return 'Use letters only in a name';
    const l = letters(v).toLowerCase();
    if (!l) return 'Enter a name with letters';
    if (RUN4.test(v.toLowerCase()) || (l.length >= 3 && new Set(l).size === 1)) return "This doesn't look like a real name";
    if (PLACEHOLDERS.has(l) || v.split(/[\s.'’()-]+/).some(mash)) return 'Enter a real name';
    return '';
  }),
  place: text((v) => {
    const l = letters(v).toLowerCase();
    if (!l) return 'Enter a place name with letters';
    if (RUN4.test(v.toLowerCase()) || (PLACEHOLDERS.has(l) && l !== 'na') || mash(l)) return 'Enter a real place name';
    return '';
  }),
  text: text((v) => {
    if (!/[\p{L}\p{N}]/u.test(v)) return 'Enter some text, not only symbols';
    const compact = v.replace(/\s/g, '').toLowerCase();
    if (compact.length >= 5 && new Set(compact).size === 1) return "This doesn't look like real text";
    return '';
  }),
  email: text((v) => {
    const local = v.slice(0, v.lastIndexOf('@'));
    const ok = EMAIL.test(v) && !local.includes('..') && !local.startsWith('.') && !local.endsWith('.') && local.length <= 64;
    return ok ? '' : 'Enter a valid email address';
  }),
  /** backend member/auth/schema.py to_e164: 10 digits starting 6-9 (India), or +country and 8-15 digits. */
  mobile(raw: string, { required = false }: Opts = {}) {
    const d = raw.trim().replace(/[\s\-()]/g, '');
    if (!d) return required ? 'Required' : '';
    const e164 = /^[6-9]\d{9}$/.test(d) ? `+91${d}` : d;
    if (!/^(\+91[6-9]\d{9}|\+(?!91)[1-9]\d{7,14})$/.test(e164)) return 'Enter a valid mobile number';
    if (new Set(e164.slice(-10)).size === 1) return 'Enter your real mobile number';
    return '';
  },
  /** Whole centimetres, 100-250 (matrimony height_cm). */
  height(raw: string) {
    const v = raw.trim();
    if (!v) return '';
    return /^\d{3}$/.test(v) && +v >= 100 && +v <= 250 ? '' : 'Height in cm, between 100 and 250';
  },
  /** HH:MM, 24-hour (biodata birth_time). */
  time(raw: string) {
    const v = raw.trim();
    return !v || /^([01]\d|2[0-3]):[0-5]\d$/.test(v) ? '' : 'Use HH:MM, 24-hour';
  },
};

/** The first problem among fields, for disabling a submit button: errors(...) || '' */
export const firstError = (...messages: string[]) => messages.find(Boolean) ?? '';
