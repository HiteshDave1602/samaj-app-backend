// node --test src/shared   (Node's built-in runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { checkControl, clean, fieldLabel, rules } from './validate.js'

test('clean: trims, single-spaces, drops control and bidi characters, keeps ZWJ', () => {
  assert.equal(clean('  Asha ‮  Patel\u0000 '), 'Asha Patel')
  assert.equal(clean('a\r\n\r\n\r\n\r\nb  c ', true), 'a\n\nb c')
  assert.equal(clean('ક્‍ષ'), 'ક્‍ષ')
})

test('personName: real names in any script pass', () => {
  for (const ok of ['Asha Patel', "D'Souza", 'Asha P. Shah', 'આશાબેન પટેલ', 'राम-लाल', 'M', 'O’Neil', 'Bharat (Late)'])
    assert.equal(rules.personName(ok), '', ok)
})

test('personName: junk, digits, markup and placeholders fail', () => {
  for (const bad of ['asdfghjkl', '!!!!', '1111111111', 'Raaaaam', 'aaa', 'test', 'N.A.', 'Ram2', '<b>x</b>', 'Qwerty Patel'])
    assert.notEqual(rules.personName(bad), '', bad)
})

test('place, text, email', () => {
  assert.equal(rules.place('Sector 21'), '')
  assert.notEqual(rules.place('1234'), '')
  assert.equal(rules.text('No'), '')
  assert.equal(rules.text('a < b & c'), '') // kept as typed; React escapes it on display
  assert.notEqual(rules.text('!!!!!!!!!'), '')
  assert.notEqual(rules.text('aaaaaaa'), '')
  assert.equal(rules.email('asha.p@example.com'), '')
  for (const bad of ['a@b', 'a..b@x.com', '.a@x.com', 'a@-x.com', 'a b@x.com']) assert.notEqual(rules.email(bad), '', bad)
})

const el = (attrs) => ({ tagName: 'INPUT', type: 'text', required: false, disabled: false, dataset: {}, ...attrs })

test('checkControl: required whitespace is empty, rules by name, opt-outs', () => {
  assert.equal(checkControl(el({ name: 'full_name', value: '   ', required: true })), "This field can't be empty")
  assert.equal(checkControl(el({ name: 'full_name', value: 'asdf' })), 'Enter a real name')
  assert.equal(checkControl(el({ name: 'full_name', value: 'Asha Patel' })), '')
  assert.equal(checkControl(el({ name: 'full_name', value: 'asdf', dataset: { rule: 'none' } })), '')
  assert.equal(checkControl(el({ name: 'password', type: 'password', value: '!!!!' })), '') // never judged
  assert.equal(checkControl(el({ name: 'notes', value: '' })), '') // optional and empty
  assert.equal(checkControl(el({ name: 'x'.repeat(5), value: 'anything' })), '') // unlisted field
})

test('fieldLabel', () => {
  assert.equal(fieldLabel('full_name'), 'Full name')
  assert.equal(fieldLabel('full_name_i18n.gu'), 'Gu')
})
