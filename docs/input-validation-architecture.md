# Input validation: architecture

How user input is checked, cleaned and rejected across the backend, the admin panels and the member app.

## The one rule

**The backend decides.** Every request body goes through a Pydantic model before any business logic or database
call. The frontends repeat the same rules only to answer faster; they are not a security boundary.

## Pieces

| Piece | File | Job |
|---|---|---|
| Field types | `backend/core/validation.py` | `PersonName`, `Place(n)`, `Text(n)`, `Email`, `Search(n)`; the `clean()` normaliser; the `Strict` base model |
| Request guard | `backend/core/guard.py` | Body size cap (413), one error shape for every 4xx/5xx, logging of rejected input |
| Request models | `backend/**/schema.py` | Every input model extends `Strict` and uses the field types above |
| Uploads | `backend/core/media.py`, `member/profile/curd.py`, `member/matrimony/curd.py`, `cityadmin/member_import/curd.py` | Size limits, file-signature checks, server-made storage keys (unchanged; already sound) |
| DB constraints | `backend/alembic/versions/*` | NOT NULL, CHECK, UNIQUE, FKs; plus `ux_family_member_person` (new) |
| Admin panels | `web-frontend/src/shared/validate.js`, `shared/api.js` (`useSubmit`, `api`) | The same rules on every form, server errors shown on the inputs |
| Member app | `app-frontend/src/lib/validate.ts`, `components/ui/form.tsx` (`Field`) | The same rules per screen, errors shown under each field |

## Flow of one request

```
client form ──► client rules (instant; skippable by an attacker)
            ──► HTTP
BodyLimit (core/guard.py)         over 1 MB JSON / ~10 MB multipart → 413, before the body is read
AdmissionLimit (core/admission.py) concurrency cap, unchanged
auth dependency                   401 / 403 (authorization stays on the backend)
Pydantic model (Strict)           1. unknown property → 422 "This field isn't accepted"
                                  2. BeforeValidator clean(): NFC, control/bidi chars out, whitespace tidied
                                  3. type, length, enum, range, pattern
                                  4. AfterValidator data-quality rule (name / place / text / email)
                                  5. model_validator cross-field rules (dates in order, ad needs media…)
curd function                     business rules (duplicates, state machine, city scope)
SQLAlchemy                        bound parameters only; DB constraints are the last line
```

Any failure at steps 1–5 is turned into the shared error response by `core/guard.py`.

## Error response

Every error keeps FastAPI's original `detail` (existing clients read it) and adds `error`:

```json
{
  "detail": [{"type": "value_error", "loc": ["body", "full_name"], "msg": "Value error, Enter a real name"}],
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the highlighted fields.",
    "fields": {"full_name": "Enter a real name"}
  }
}
```

- `code`: `VALIDATION_ERROR`, `MALFORMED_JSON`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`,
  `PAYLOAD_TOO_LARGE`, `RATE_LIMITED`, `INTERNAL_ERROR`, …, or an SOP code such as `ERR_IMG_UL` when the detail starts with one.
- `fields`: only on 422. Keys are the field path (`full_name`, `full_name_i18n.gu`, `filters.age_min`); rules about
  the whole body use the key `body`.
- A 422 never echoes the submitted value (`input` and `ctx` are removed), so passwords and payloads don't bounce back.
- Unhandled exceptions return a generic 500 in the same shape; the traceback goes to the server log only.

## Who does what

| Concern | Frontend | Backend |
|---|---|---|
| Required, length, format, data quality | Instant feedback, blocks the submit button | Enforced |
| Unknown / extra properties | — | Rejected (`Strict`) |
| Authorization, city scope | Hides what you can't do | Enforced in dependencies and curd |
| Duplicates | Busy-locked buttons, one submit at a time | Business checks + unique indexes |
| File type and size | `accept=` hint and picker types | Signature (magic bytes) and size checked on the bytes |
| HTML / script in text | Rendered as text by React / React Native | Stored as typed; never rendered as HTML |
| SQL | — | ORM with bound parameters; no string-built SQL |
