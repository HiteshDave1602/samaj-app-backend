// node --test src/lib/validate.test.ts   (Node 23.6+ runs TypeScript directly; no extra packages)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { clean, firstError, rules } from './validate.ts';

test('clean', () => {
  assert.equal(clean('  Asha ‮  Patel\u0000 '), 'Asha Patel');
  assert.equal(clean('a\r\n\r\n\r\n\r\nb  c ', true), 'a\n\nb c');
});

test('personName: real names pass, junk fails, length and required', () => {
  for (const ok of ['Asha Patel', "D'Souza", 'આશાબેન પટેલ', 'राम-लाल', 'Bharat (Late)']) assert.equal(rules.personName(ok), '', ok);
  for (const bad of ['asdfghjkl', '!!!!', '1111111111', 'Raaaaam', 'test', 'Ram2', '<b>x</b>']) assert.notEqual(rules.personName(bad), '', bad);
  assert.equal(rules.personName('   '), ''); // optional + empty is fine
  assert.equal(rules.personName('   ', { required: true }), 'Required');
  assert.equal(rules.personName('Ab'.repeat(60)), '');
  assert.equal(rules.personName('Ab'.repeat(60) + 'c'), 'Keep it to 120 characters');
});

test('mobile: same rules as to_e164', () => {
  for (const ok of ['9876543210', '98765 43210', '+91-9876543210', '+14155550123']) assert.equal(rules.mobile(ok), '', ok);
  for (const bad of ['12345', '5876543210', '9999999999', '+91123', 'abc']) assert.notEqual(rules.mobile(bad), '', bad);
  assert.equal(rules.mobile(''), '');
});

test('text, place, email, height, time', () => {
  assert.equal(rules.text('a < b & c'), '');
  assert.notEqual(rules.text('!!!!!!!!!'), '');
  assert.equal(rules.text('x'.repeat(10), { max: 5 }), 'Keep it to 5 characters');
  assert.equal(rules.place('Sector 21'), '');
  assert.notEqual(rules.place('1234'), '');
  assert.equal(rules.email('asha.p@example.com'), '');
  assert.notEqual(rules.email('a..b@x.com'), '');
  assert.equal(rules.height('168'), '');
  for (const bad of ['99', '251', '16a', '1.6']) assert.notEqual(rules.height(bad), '', bad);
  assert.equal(rules.time('23:59'), '');
  assert.notEqual(rules.time('24:00'), '');
  assert.equal(firstError('', 'x', 'y'), 'x');
});
