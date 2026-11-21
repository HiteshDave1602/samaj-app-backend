# Input security

What protects each class of attack, and where. Input cleaning is one layer of several: none of these rely on it
alone.

## XSS and HTML injection

- **Output encoding is the defence.** Admin panels (React) and the member app (React Native `<Text>`) render every
  value as text. There is no `dangerouslySetInnerHTML`, `innerHTML` or WebView anywhere (checked 2026-11-21);
  keep it that way. No feature accepts rich text, so there is no HTML sanitiser to maintain.
- Free text (news, addresses, reasons) is stored exactly as typed, `<script>` included, and shown as literal text.
  Stripping it would mangle legitimate text such as "a < b".
- Names reject `<`, `>` and other symbols through the name rule, as data quality and defence in depth.
- API responses are `application/json`; uploaded images are served from `/media` with server-made names and an
  image extension only.

## SQL injection

- All queries go through the SQLAlchemy ORM / Core with bound parameters. `icontains(..., autoescape=True)` escapes
  `%` and `_` in search text.
- The only f-string SQL is in two migrations, interpolating constant table names from the code, never input.
- `test_validation.py` sends `' OR 1=1 --` and `'; DROP TABLE …` as search text and checks they match nothing.

## Malformed JSON, wrong types, unexpected properties, mass assignment

- A body that isn't valid JSON gives 422 `MALFORMED_JSON`.
- Every input model extends `Strict` (`extra="forbid"`): a property the endpoint doesn't declare gives 422 instead
  of being ignored. Fields such as `status`, `city_id`, `member_id` or `is_household_head` can't be smuggled into a
  profile update.
- Models are copied into ORM rows field by field or by `model_dump()` of a strict model, never from raw request dicts.

## Parameter tampering and authorization

- IDs in paths and queries are typed (`UUID`, `date`, enums). Ownership and city scope are checked on the server in
  dependencies and curd (`require_city_admin`, `get_active_member`, `Denied` → `security_event`).
- Pagination is bounded (`limit` ≤ 200, imports' row listing ≤ 1000).

## Request size

- `core/guard.BodyLimit`: JSON bodies up to 1 MB; multipart up to 10 MB + 64 KB. An oversized `Content-Length` gets
  413 before anything is read; a chunked body without one is counted as it streams and cut off at the limit.
- Per-endpoint limits then apply: images 5 MB (news/ads), photos and ID documents 2 MB, imports 10 MB and 50 000 rows.

## File uploads

| Check | Where |
|---|---|
| Size | `read(MAX + 1)` bounded reads in each upload route, then a 413 with the SOP code `ERR_IMG_UL` |
| Real type | File signature (magic bytes): PNG header + IHDR, JPEG SOI + a frame header, `%PDF-` for ID documents. The client's filename and MIME type are ignored |
| Storage name | Server-made `uuid4().hex` (+ `.png`/`.jpg` for public media), checked against a strict regex before any disk access, so no path traversal |
| Private files | ID documents, matrimony photos and import files are Fernet-encrypted at rest and served only through endpoints that check access |
| Spreadsheets | `.csv` must be UTF-8; `.xlsx` opened read-only with `data_only=True` (formulas are not evaluated); headers must match the template |
| Formula injection on export | Export cells that would start a formula are forced to text; audit CSV cells are neutralised |
| Authorization | Every upload route requires the right member or admin dependency |
| Temporary files | Starlette spools multipart parts to temp files and closes them after the request; nothing else writes temp files |

OCR is not used anywhere in this codebase, so there is no extracted-text path to validate.

## Logging and monitoring

Logger `samaj.input` (structured `key=value`):

| Event | Level | Fields logged |
|---|---|---|
| `input_rejected` | INFO; WARNING for malformed JSON, unexpected properties or non-object bodies | method, path, client IP, field names, error types |
| `upload_rejected` | WARNING | method, path, client IP, status |
| `body_too_large` | WARNING | path, declared length |
| `unhandled` | ERROR with traceback | method, path |

Never logged: submitted values, passwords, tokens, file contents. Cross-city and ID-document denials continue to go
to the `security_event` table. Nobody is blocked for making mistakes; the existing per-IP and per-account rate limits
(429) are the only throttle.
