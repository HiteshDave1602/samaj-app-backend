# Input validation: rules

Source of truth: `backend/core/validation.py`. Mirrors: `web-frontend/src/shared/validate.js`,
`app-frontend/src/lib/validate.ts`. Change all three together.

## Cleaning (every text field, before any check)

| Step | Single-line fields | Multiline fields (address, body, about…) |
|---|---|---|
| Unicode | NFC (so "é" typed two ways is one value) | same |
| Control characters (U+0000–001F, 007F–009F) | removed | removed, except newline and tab |
| Bidi overrides (U+202A–202E, 2066–2069) | removed (used to disguise text) | removed |
| ZWJ / ZWNJ (U+200C/D) | **kept**: Gujarati and Hindi need them | kept |
| Whitespace | trimmed, runs become one space | each line trimmed, runs of spaces become one, at most one blank line in a row |

Passwords, tokens, OTP codes and IDs are never cleaned.

## Field types

| Type | Length | Allowed | Rejected (message) |
|---|---|---|---|
| `PersonName` | 1–120 | Letters of any script with their vowel signs, space, `. ' ’ - ( )` | Digits or symbols ("Use letters only in a name"); no letters; a character 4+ times in a row or one letter repeated ("This doesn't look like a real name"); placeholders such as test, asdf, dummy, n/a, unknown; keyboard or alphabet runs of 4+ such as qwerty, asdf, abcd ("Enter a real name") |
| `Place(n)` | 1–n | Anything readable; digits allowed ("Sector 21") | No letters; 4+ repeats; placeholders; keyboard runs ("Enter a real place name") |
| `Text(n)` | 1–n | Everything, including `< > & / # "` | Only symbols ("Enter some text, not only symbols"); one character over and over, 5+ ("This doesn't look like real text") |
| `Email` | ≤ 254 (local part ≤ 64) | `local@domain.tld`, letters-only TLD of 2+ | Spaces, `..`, leading or trailing dot, missing TLD. The domain is lower-cased; the local part is kept as typed |
| `Search(n, min)` | min–n | Everything (cleaned only) | Nothing beyond length: search text is data |
| `Mobile` | — | 10 digits starting 6–9 (gets +91), or `+country` with 8–15 digits | Anything else; ten identical digits such as 9999999999 ("Enter your real mobile number") |

Deliberately **not** rejected: `test@test.com`-style emails (real people use odd addresses), sequential phone
numbers (the import template's own example is 9876543210), short names like "M" or "Om", and markup in free text
(it is displayed as text, see `input-security.md`).

## Fields by module

| Endpoint(s) | Field | Rule |
|---|---|---|
| `POST /member/auth/otp/send`, `/otp/verify` | mobile | Mobile |
| | code | exactly 6 digits |
| `POST /member/auth/register` | full_name, family_name | PersonName |
| | native_place | Place(120), optional |
| | address | Text(500), multiline |
| | dob | a real date from 1900-01-01 to today |
| | gender, language | enum |
| | consent | must be `true` |
| | registration_ticket | ≤ 500 chars, sealed and time-limited |
| `PUT /member/me` | full_name, family_name, `*_i18n` names | PersonName (send only what changes) |
| | native_place, native_place_i18n | Place(120) |
| | address | Text(500), multiline |
| `POST /member/family` | full_name | PersonName; relationship, gender enums; dob as above |
| `POST/PUT /member/matrimony/profile` | education_detail 120, occupation 80, gotra 60 | Text |
| | about | Text(500), multiline |
| | height_cm | 100–250 |
| `PUT /member/matrimony/biodata` | father_name, mother_name | PersonName |
| | birth_place | Place(120) |
| | rashi 40, nakshatra 40, gotra 60, occupations 120, annual_income 60 | Text |
| | siblings 300, residence_address 500, expectations 1000 | Text, multiline |
| | birth_time | HH:MM, 24-hour |
| | contact_phone / contact_email | Mobile / Email |
| `POST /member/news` | title | Text(200) |
| | body | Text(10 000), multiline |
| | media_key, extra_media_keys (≤ 5) | ≤ 40 chars, must be an uploaded image |
| Admin content create/update | title, body | as member news |
| All reject actions | reason | Text(500), multiline |
| `PUT /cityadmin/panchang/{date}` | tithi, nakshatra, yoga | Text(40) |
| `POST/PUT /superadmin/cities` | name / state | Place(80) / Place(60) |
| `POST/PUT /superadmin/city-admins` | full_name | PersonName |
| | email | Email |
| | password | 12–128 chars (never cleaned) |
| `POST /admin/auth/login` | email | lenient older format (looks an account up; must not lock anyone out) |
| `GET /member/directory` | name, family_name | Search(120, min 2) |
| `GET /member/matrimony/profiles` | q | Search(120, min 2); ages 18–100 |
| `GET /cityadmin/members`, export filters | q, area, family_name | Search(120) |
| `GET /superadmin/audit-logs` | action | letters and `_` only, ≤ 40 |
| Spreadsheet imports (both) | every cell | cleaned like the API |
| City Admin import | full_name, family_name / native_place | PersonName / Place, reported per row in the dry run |
| Directory import | Name | PersonName, reported per row in the dry run |

## Data-quality policies

- Rules are per field type, so free text (addresses, notes, news) is never held to name rules.
- A refused value is never silently changed: the person or the import dry run is told which field and why.
- Imports report failing rows in the dry run; the admin fixes the sheet. Nothing is dropped quietly.
- In the app, a saved value that today's rules refuse is flagged as soon as the screen opens. On the profile screen
  only changed fields are judged, so an old value never blocks saving something else.

## Duplicates

| What | How |
|---|---|
| Mobile number per member | `UNIQUE(mobile_hash)` (existing) |
| Admin email | `UNIQUE(email)` on CITEXT, so case-insensitive (existing) |
| City | `UNIQUE(name, state)` (existing) |
| Family member per household | Friendly 409 check plus **new** partial unique index `ux_family_member_person` on (household, lower(name), dob) where not rejected and dob is set, so four identical requests at once give one 201 and three 409s |
| Member news | 409 if the same member already has the same title and body waiting for approval (a business rule, so no index) |
| Biodata request, matrimony photo slot, panchang day, consent | existing unique indexes |
| Import rows | Same-file duplicates flagged in the dry run (existing) |
| Double submit in the UI | Buttons lock while busy; `useSubmit` also ignores a second submit while one is running |
