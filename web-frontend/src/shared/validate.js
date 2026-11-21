// Instant feedback that mirrors backend/core/validation.py (keep the two in step; app-frontend/src/lib/validate.ts too).
// The server re-checks everything: this only saves a round trip. docs/input-validation-rules.md lists the rules.

const BIDI = /[‪-‮⁦-⁩]/g // display-order overrides, used to disguise text
// eslint-disable-next-line no-control-regex -- removing control characters is the point
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g // keeps \t \n \r for the line handling below
const RUN4 = /(.)\1{3}/u
const KEYBOARD = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm', 'abcdefghijklmnopqrstuvwxyz', '1234567890']
const PLACEHOLDERS = new Set(['test', 'testing', 'tester', 'asdf', 'qwerty', 'dummy', 'sample', 'fake', 'name', 'fullname',
  'firstname', 'lastname', 'na', 'none', 'null', 'undefined', 'unknown', 'abc', 'xyz', 'xxx', 'noname'])
// ZWNJ/ZWJ (U+200C/D) shape Gujarati and Hindi conjuncts, so names may contain them
// eslint-disable-next-line no-misleading-character-class
const NAME_CHARS = /^[\p{L}\p{M}‌‍ .'’()-]+$/u
const EMAIL = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$/

/** NFC, no control characters, trimmed; one line: single spaces; multiline: tidy lines, one blank line at most. */
export function clean(v, multiline = false) {
  const s = String(v ?? '').normalize('NFC').replace(BIDI, '').replace(/\r\n?/g, '\n').replace(CONTROL, '')
  if (!multiline) return s.split(/\s+/).filter(Boolean).join(' ')
  return s.split('\n').map((l) => l.replace(/[^\S\n]+/g, ' ').trim()).join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

const letters = (v) => (v.match(/\p{L}/gu) ?? []).join('')
const mash = (w) => w.length >= 4 && KEYBOARD.some((r) => r.includes(w.toLowerCase()) || [...r].reverse().join('').includes(w.toLowerCase()))

// Each rule: cleaned value -> '' when fine, else the message the server would give.
export const rules = {
  personName(v) {
    if (!NAME_CHARS.test(v)) return 'Use letters only in a name'
    const l = letters(v).toLowerCase()
    if (!l) return 'Enter a name with letters'
    if (RUN4.test(v.toLowerCase()) || (l.length >= 3 && new Set(l).size === 1)) return "This doesn't look like a real name"
    if (PLACEHOLDERS.has(l) || v.split(/[\s.'’()-]+/).some(mash)) return 'Enter a real name'
    return ''
  },
  place(v) {
    const l = letters(v).toLowerCase()
    if (!l) return 'Enter a place name with letters'
    if (RUN4.test(v.toLowerCase()) || (PLACEHOLDERS.has(l) && l !== 'na') || mash(l)) return 'Enter a real place name'
    return ''
  },
  text(v) {
    if (!/[\p{L}\p{N}]/u.test(v)) return 'Enter some text, not only symbols'
    const compact = v.replace(/[\s]/g, '').toLowerCase()
    if (compact.length >= 5 && new Set(compact).size === 1) return "This doesn't look like real text"
    return ''
  },
  email(v) {
    const local = v.slice(0, v.lastIndexOf('@'))
    const ok = EMAIL.test(v) && !local.includes('..') && !local.startsWith('.') && !local.endsWith('.') && local.length <= 64
    return ok ? '' : 'Enter a valid email address'
  },
}

// Admin-panel form fields by their `name` attribute -> rule. A field not listed gets only the browser's own checks.
export const FIELD_RULES = {
  full_name: rules.personName, family_name: rules.personName,
  name: rules.place, state: rules.place, // the Cities form: city name and state
  email: rules.email,
  title: rules.text, body: rules.text, reason: rules.text, tithi: rules.text, nakshatra: rules.text, yoga: rules.text,
}

/** The message for one form control, '' if it's fine. Whitespace-only counts as empty for required fields.
 * data-rule="personName" (etc.) picks a rule by hand; data-rule="none" leaves only the browser's checks. */
export function checkControl(el) {
  if (!el.name || el.disabled || !['INPUT', 'TEXTAREA'].includes(el.tagName) || ['password', 'file', 'checkbox', 'radio', 'hidden'].includes(el.type)) return ''
  const v = clean(el.value, el.tagName === 'TEXTAREA')
  if (!v) return el.required ? "This field can't be empty" : ''
  const rule = el.dataset.rule ? rules[el.dataset.rule] : FIELD_RULES[el.name]
  return rule?.(v) ?? ''
}

/** "full_name" -> "Full name" for error summaries. */
export const fieldLabel = (key) => {
  const last = String(key).split('.').pop().replace(/_/g, ' ')
  return last.charAt(0).toUpperCase() + last.slice(1)
}
