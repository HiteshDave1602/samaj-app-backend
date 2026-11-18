// k6 load test for the member directory and matrimony search (docs/search.md, "Load testing").
// Run through loadtest/run.ps1, or by hand:
//   docker run --rm -v ${PWD}/loadtest:/scripts -e BASE=http://host.docker.internal:8000 -e VUS=100 \
//     grafana/k6:1.4.2 run /scripts/search.js
// Env: VUS (concurrent users), DURATION (default 45s), MIX = mixed | same | filters | large, LABEL (summary file name)
import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter } from 'k6/metrics';

const tokens = new SharedArray('tokens', () => JSON.parse(open('./.out/tokens.json')));
const W = JSON.parse(open('./.out/words.json'));
const BASE = __ENV.BASE || 'http://host.docker.internal:8000';
const MIX = __ENV.MIX || 'mixed';
const leaked = new Counter('hidden_members_returned'); // must stay 0: pending/archived people are never listed
const timeouts = new Counter('timeouts'); // no response within 15 s
const KINDS = ['dir_name', 'dir_partial', 'dir_typo', 'dir_gujarati', 'dir_family_city', 'dir_deep', 'dir_same',
  'dir_broad', 'dir_all', 'matrimony'];

export const options = {
  scenarios: {
    users: { executor: 'constant-vus', vus: Number(__ENV.VUS || 10), duration: __ENV.DURATION || '45s' },
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  // the empty per-kind thresholds only make k6 report latency per request kind
  thresholds: Object.assign({ hidden_members_returned: ['count==0'] },
    ...KINDS.map((k) => ({ [`http_req_duration{kind:${k}}`]: [] }))),
};

const pick = (a) => a[Math.floor(Math.random() * a.length)];
const qs = (o) => Object.entries(o).flatMap(([k, v]) => (Array.isArray(v) ? v : [v]).map((x) => `${k}=${encodeURIComponent(x)}`)).join('&');
const typo = (s) => { const i = 1 + Math.floor(Math.random() * (s.length - 2)); return s.slice(0, i) + s.slice(i + 1); };

function request() {
  const r = Math.random();
  if (MIX === 'same') return ['dir_same', `/member/directory?${qs({ name: 'Rahul', family_name: 'Patel' })}`];
  if (MIX === 'large') { // broad queries over the whole community, paged deep
    return r < 0.5
      ? ['dir_broad', `/member/directory?${qs({ family_name: pick(W.surnames), offset: 20 * Math.floor(Math.random() * 25), limit: 20 })}`]
      : ['dir_all', `/member/directory?${qs({ offset: 50 * Math.floor(Math.random() * 100), limit: 50 })}`];
  }
  if (MIX === 'filters' || r < 0.25) { // matrimony filters, sometimes free text
    const p = { gender: pick(['MALE', 'FEMALE']), age_min: 21 + Math.floor(Math.random() * 6), age_max: 30 + Math.floor(Math.random() * 8),
      education_level: [pick(W.edu), pick(W.edu)], city_id: [pick(W.cities), pick(W.cities), pick(W.cities)] };
    if (Math.random() < 0.3) p.q = pick(W.jobs).split(' ')[0];
    return ['matrimony', `/member/matrimony/profiles?${qs(p)}`];
  }
  if (r < 0.55) return ['dir_name', `/member/directory?${qs({ name: pick(W.first) })}`];
  if (r < 0.65) return ['dir_partial', `/member/directory?${qs({ name: pick(W.first).slice(0, 3) })}`];
  if (r < 0.72) return ['dir_typo', `/member/directory?${qs({ name: typo(pick(W.first.filter((f) => f.length >= 5))) })}`];
  if (r < 0.77) return ['dir_gujarati', `/member/directory?${qs({ name: pick(W.gu_first) })}`];
  if (r < 0.95) return ['dir_family_city', `/member/directory?${qs({ family_name: pick(W.surnames), city_id: pick(W.cities) })}`];
  return ['dir_deep', `/member/directory?${qs({ family_name: pick(W.surnames), offset: 200 })}`];
}

export default function () {
  if (Math.random() < 0.02) { // auth: no token is 401, a pending member is 403, on every backend
    const expect = { responseCallback: http.expectedStatuses(401, 403), tags: { kind: 'auth' } };
    const anon = http.get(`${BASE}/member/directory?name=Rahul`, expect);
    const pend = http.get(`${BASE}/member/directory?name=Rahul`, Object.assign({ headers: { Authorization: `Bearer ${W.pending_token}` } }, expect));
    check(null, { 'anonymous 401': () => anon.status === 401, 'pending 403': () => pend.status === 403 });
  }
  const [kind, path] = request();
  const res = http.get(`${BASE}${path}`, { headers: { Authorization: `Bearer ${tokens[(__VU - 1) % tokens.length]}` }, tags: { kind }, timeout: '15s' });
  check(res, { 'status 200': (x) => x.status === 200 });
  if (res.status === 0) timeouts.add(1);
  if (res.status === 200 && res.body.includes('Zzhidden')) leaked.add(1);
  sleep(0.5 + Math.random()); // think time: one search every ~1 s per user
}

export function handleSummary(data) {
  const label = __ENV.LABEL || `${MIX}-${__ENV.VUS}`;
  return { [`/scripts/.out/summary-${label}.json`]: JSON.stringify(data) };
}
