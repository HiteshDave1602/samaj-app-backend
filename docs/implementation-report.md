# Input validation: implementation report

Date: 2026-11-21. Branch: `kamya`.

## Audit summary

| Area | Stack | State found | Done |
|---|---|---|---|
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL, Alembic | Every body already went through Pydantic with lengths and enums. Extra properties were silently dropped, there was no Unicode or control-character cleaning, no data-quality rules, no body size cap, and FastAPI's 422 echoed submitted values | Shared field types, `Strict` models everywhere, error envelope, body cap, logging, a duplicate index |
| Admin panels | React 19 + Vite, no form library | Native `required`/`maxLength` on every form via one `useSubmit` hook; the 422 summary lost field names | Shared rules in `useSubmit`, server errors on the inputs, double-submit guard, `:user-invalid` styling |
| Member app | Expo / React Native, no form library | Required-field checks, busy-locked buttons; no length or quality checks, no per-field errors | `Field error`, shared rules on every form screen |
| Uploads | 5 endpoints | Already sound: bounded reads, magic-byte checks, random keys, encrypted private store | Covered by the new body cap and new tests; no code change needed |
| Database | 22 migrations | NOT NULL, CHECK (~60) and UNIQUE constraints already broad | One partial unique index for the family-request race |

No Zod or other validation library exists in either frontend, and none was added.

### Input points covered

**Request bodies (all now `Strict`):** admin login, MFA verify, MFA ticket, change password; member OTP send and
verify, register, refresh; profile update; family request; matrimony profile create and update; biodata; member news;
content create and update (City and Super Admin); reject reason (members, content, family additions, matrimony
profiles, photos); bulk approve; export; import conflict resolve; panchang edit; city create and update; City Admin
create, update and password reset.

**Query parameters:** directory `name`/`family_name`, matrimony `q`, member lists `q`, export filters (now cleaned
`Search` types); audit `action` (pattern). All other query parameters were already typed and bounded.

**Uploads:** news/ad media (3 routes), profile photo, ID document, matrimony photo, member import, directory import.

**Endpoints with no input body** (approve, withdraw, mark-read, logout and so on) take only typed path IDs.

## Files created

| File | Purpose |
|---|---|
| `backend/core/validation.py` | Cleaning, field types, `Strict` base, rule self-check |
| `backend/core/guard.py` | Body size cap, error envelope, 500 handler, input logging |
| `backend/alembic/versions/f8a1c3e5b7d9_family_member_unique_person.py` | `ux_family_member_person` |
| `backend/test_validation.py` | Security and validation tests |
| `web-frontend/src/shared/validate.js`, `validate.test.js` | Admin-panel rules and tests |
| `app-frontend/src/lib/validate.ts`, `validate.test.ts` | App rules and tests |
| `docs/input-validation-*.md`, `docs/input-security.md`, this file, `docs/developer-integration-guide.md` | Documentation |

## Files modified

- **Backend wiring:** `main.py` (guard), `auth/deps.py` (403s in the shared shape).
- **Schemas** (field types and `Strict`): `auth/schema.py`, `member/auth/schema.py` (adds the placeholder-mobile
  check), `member/profile/schema.py`, `member/family/schema.py`, `member/matrimony/schema.py`,
  `cityadmin/content/schema.py`, `cityadmin/member_approval/schema.py`, `cityadmin/member_export/schema.py`,
  `cityadmin/member_import/schema.py`, `cityadmin/panchang/schema.py`, `superadmin/city/schema.py`,
  `superadmin/city_admin/schema.py`, `superadmin/audit_log/schema.py`.
- **Routes and logic:** `member/directory/api.py`, `member/matrimony/api.py` (search types);
  `member/family/curd.py` (`IntegrityError` → 409); `cityadmin/content/curd.py` (duplicate pending news → 409);
  `cityadmin/member_import/curd.py`, `superadmin/member_import/curd.py` (cell cleaning and name rules in the dry run);
  `member/profile/model.py` (declares the new index).
- **Admin panels:** `shared/api.js`, `shared/ui.jsx`, `shared/Login.jsx`, `city-admin/pages/Export.jsx`.
- **App:** `components/ui/form.tsx`, `lib/api.ts`, `app/register.tsx`, `app/login.tsx`, `app/edit-profile.tsx`,
  `app/(app)/profile/add-member.tsx`, `app/(app)/matrimony/create.tsx`, `app/(app)/matrimony/biodata.tsx`,
  `app/(app)/news/create.tsx`, `tsconfig.json` (excludes the Node-run test files).
- **Existing tests:** `test_biodata.py`, `test_directory_import.py` and `test_import_export.py` used digits or a
  spreadsheet formula *inside people's names* as fixtures; the new name rule rightly refuses those. The fixtures now
  use letter-only markers, and the formula fixture moved to the address column, so export formula-neutralising is
  still tested. `test_permissions.py` had a stale assertion from before this work (missing `mfa_enrolled_at`).

## Dependencies

None added to any app. `pytest` and `pyflakes` were installed into the local venv only to run checks; neither is in
`requirements.txt`.

## Database migration

`f8a1c3e5b7d9`: a partial unique index on `family_member (household_id, lower(full_name), dob) WHERE status <>
'REJECTED' AND dob IS NOT NULL`. Not destructive. Before creating the index it counts existing duplicates; if there are
any, it stops with the query that finds them and changes nothing. The dev database had 0 duplicates among 6 888 rows.
Tested `upgrade`, `downgrade -1` and `upgrade` again.

No other constraint was needed: the remaining columns already have NOT NULL, length, CHECK and FK constraints that
match the API rules.

## Backward compatibility

- Error responses keep `detail` exactly as before; `error` is added alongside. Both frontends still read `detail`
  when `error` is missing.
- The admin login email stays as lenient as before, so no existing admin can be locked out.
- All bodies the current frontends send were checked against the `Strict` models. None send extra properties.
- Stored data is untouched. A stored value that a new rule refuses is only refused when someone re-submits it, and the
  app flags it on screen.

## Test results (2026-11-21, dev database)

| Suite | Result |
|---|---|
| `python -m core.validation` | pass |
| `test_validation.py` (new) | pass: envelope; malformed JSON; wrong types; mass assignment (`status`, `city_id`, `is_household_head`, `member_id`); boundaries 120/121; whitespace-only; Unicode and bidi cleaning; Gujarati names; no echo of a submitted password; registration rules; XSS kept as text; duplicate news 409; SQL injection payloads; oversized body by Content-Length and chunked; oversized photo; GIF, HTML, EXE and SVG disguised as PNG; PDF as a photo; 4 concurrent identical family requests → exactly one 201; direct duplicate insert refused by the index |
| Existing backend scripts (19) | 17 pass. 2 fail exactly as before this work, for environment reasons: `test_content.py` (a leftover "testing" content row in the dev DB) and `test_search.py` (trips its own per-process search rate limit) |
| 10 000-row import performance | 40.0 s on its own (baseline 43.7 s, budget 120 s) |
| Web rules (`node --test`) | 6/6 pass; `eslint` clean; `vite build` OK |
| App rules (`node --test`) | 4/4 pass; `tsc --noEmit` clean; `expo lint` 0 errors (2 older warnings) |
| Browser check, Super Admin panel (Chrome) | Junk name stopped in the browser with 0 requests and the field marked red; editing clears the message; whitespace-only = empty; a Gujarati name passes; a server 422 lands on the input and in the summary ("Full name: Enter a real name") |

## Known limitations and pending items

- **No automated UI test runner** exists in either frontend. The rule modules are unit-tested and the admin form flow
  was checked by hand in a browser. The app screens were type-checked and linted but **not run on a device or
  emulator** in this session.
- **Rules live in three files** (Python, JS, TS). Separate packages and bundlers (Vite, Metro) make one shared file
  awkward. The rule tests use the same cases, but nothing automatically checks that the three stay in step.
- **Repeated suspicious input** is logged per request at WARNING, but not counted or alerted on in-process. Aggregate
  `samaj.input` warnings in whatever log tool production uses.
- **The 1 MB JSON cap** is global. An endpoint that ever needs a bigger JSON body needs a per-path limit in
  `BodyLimit`.
- **Directory-import name rule:** sheets with digits or symbols in a person's name (for example "Ramesh 2") now show
  those rows as errors in the dry run. That is intended, but expect some first-import friction with legacy sheets.
- **README** still says to run tests with `pytest`. The scripts actually need to be run one by one (see the developer
  guide). Not changed here.
- **Malware scanning** of uploads (for example ClamAV) is not in place. The signature checks keep uploads to
  PNG/JPEG/PDF, and PDFs are only served back to admins, encrypted at rest.
