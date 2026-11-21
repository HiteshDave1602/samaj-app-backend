# Developer guide: using the validation engine

## A new API endpoint

```python
from core.validation import Email, PersonName, Place, Search, Strict, Text

class EventCreate(Strict):                     # Strict: unknown properties are a 422
    title: Text(200)                           # one line, cleaned, must say something
    details: Text(5_000, multiline=True) | None = None
    organiser: PersonName
    venue: Place(120)
    contact_email: Email | None = None
    seats: int = Field(ge=1, le=10_000)
    kind: Literal["PUJA", "MEETING"]           # enums are Literals
```

- Read input only through a model like this. Never `await request.json()` in a route.
- Query parameters: `name: Search(120, 2) | None = None`.
- Cross-field rules go in a `@model_validator(mode="after")` that raises `ValueError("…")`; the message lands in
  `error.fields.body`.
- Business-rule failures (`HTTPException(409, "…")`) need no extra work: `core/guard.py` gives them the shared shape.
- Uniqueness that must hold under concurrency needs a unique index (or partial unique index) in a migration. Keep the
  friendly pre-check, and catch `IntegrityError` on commit and answer with the same 409 (see
  `member/family/curd.request_addition`).
- Uploads: read with `file.file.read(LIMIT + 1)`, check the size, check the bytes with `core.media.image_info` (or a
  signature check of your own), store with `core.media.save` / `core.private_files.save`. Never use the client's filename.
- Output models (`…Out`) stay plain `BaseModel`; `Strict` is for input only.

## A new rule

1. Add a function to `backend/core/validation.py` that takes the cleaned string and returns it or raises
   `ValueError("message people will read")`. Add cases to its `__main__` self-check.
2. Wrap it in a type: `MyType = _str(max_len, min_len, multiline, my_rule)`.
3. Mirror it in `web-frontend/src/shared/validate.js` (`rules`) and `app-frontend/src/lib/validate.ts` (`rules`), with
   the same message, and add cases to their `*.test.*` files.
4. Document it in `docs/input-validation-rules.md`.

Before tightening a rule, check existing data: a rule an existing row fails blocks people from re-saving that row.

## A new admin-panel form

Use `useSubmit` and give inputs a `name`. That is all:

```jsx
const { onSubmit, busy, error } = useSubmit(async (f) => api('/superadmin/things', { method: 'POST', body: f }))
<form onSubmit={onSubmit}>
  <Field label="Full name"><input name="full_name" required maxLength={120} className={inputCls} /></Field>
  <ErrorText>{error}</ErrorText>
  <FormActions busy={busy} onCancel={onClose} />
</form>
```

- `required`, `maxLength`, `type="email"` etc. are checked by the browser.
- Fields named in `FIELD_RULES` (`full_name`, `email`, `title`, `body`, `reason`, …) get the shared rule. Choose one
  by hand with `data-rule="personName"`, or opt out with `data-rule="none"` (search filters, login).
- On a 422 the server's message is put on the matching input and summarised in `error`.
- `inputCls` shows the red border only after the person has touched the field.
- `useSubmit` runs one submission at a time.

## A new app screen

```tsx
import { rules } from '@/lib/validate';

const nameError = rules.personName(name, { required: true });
<Field label="Full name" value={name} onChangeText={setName} maxLength={120} error={nameError} />
<Button title="Save" disabled={busy || !!nameError} onPress={save} />
```

- `Field` shows the message after the person leaves the field. Pass `showError` for a value loaded from the server
  that today's rules refuse, so a disabled button is never unexplained.
- Rule options: `{ required, max, multiline }`. Also `rules.mobile`, `rules.height`, `rules.time`.
- `api()` errors carry `.message` ("Full name: Enter a real name") and `.fields`.

## Running the checks

```powershell
# backend (from backend/): each test file is a script against the dev database
python -m core.validation        # rule self-check
python test_validation.py        # security and validation suite
# all of them (PowerShell):
Get-ChildItem test_*.py | ForEach-Object { python $_.Name }

# web (from web-frontend/)
node --test src/shared/validate.test.js
# app (from app-frontend/; Node 23.6+)
node --test src/lib/validate.test.ts
```

Run the backend scripts one by one, not with one `pytest` process: they run at import time and share in-process rate
limits. On Windows, set `PYTHONIOENCODING=utf-8` for scripts that print Gujarati.
