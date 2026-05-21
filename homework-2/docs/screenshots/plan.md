# Plan: Homework 2 — Tasks 1–3 (Ticket Support System)

## Context

The `homework-2/` directory is currently empty except for `TASKS.md` and a placeholder `README.md`. We are building from scratch a customer support ticket system covering **Tasks 1–3** of the spec:

1. REST API for tickets with multi-format (CSV/JSON/XML) bulk import.
2. Rule-based auto-classification (category + priority + confidence + reasoning).
3. Jest test suite achieving **>85% coverage** across API, model, importers, classifier, integration, and performance benchmarks.

Stack (confirmed with user): **Node.js + Express + TypeScript**, **in-memory store**, **rule-based classifier**, **Jest + supertest**.

Tasks 4 (docs) and 5 (extended integration/perf) are out of scope for this plan.

---

## Target Project Layout

```
homework-2/
├── package.json
├── tsconfig.json
├── jest.config.ts
├── .gitignore
├── src/
│   ├── index.ts                 # server bootstrap (app.listen)
│   ├── app.ts                   # express app factory (testable, no listen)
│   ├── config.ts                # env + constants
│   ├── types/
│   │   └── ticket.ts            # Ticket, enums, DTOs (Zod-inferred)
│   ├── models/
│   │   └── ticket.schema.ts     # Zod schemas: TicketCreate, TicketUpdate, TicketImport
│   ├── store/
│   │   └── ticketStore.ts       # in-memory Map<string, Ticket> CRUD + filtering
│   ├── importers/
│   │   ├── index.ts             # dispatch by content-type / extension
│   │   ├── csvImporter.ts       # csv-parse/sync
│   │   ├── jsonImporter.ts
│   │   └── xmlImporter.ts       # fast-xml-parser
│   ├── classifier/
│   │   ├── rules.ts             # keyword maps for category + priority
│   │   ├── classifier.ts        # classify(ticket) -> ClassificationResult
│   │   └── log.ts               # in-memory decision log
│   ├── routes/
│   │   └── tickets.ts           # all /tickets endpoints
│   ├── middleware/
│   │   ├── errorHandler.ts      # central error -> JSON
│   │   └── upload.ts            # multer memoryStorage for /import
│   └── utils/
│       └── http.ts              # HttpError class, asyncHandler wrapper
└── tests/
    ├── fixtures/
    │   ├── tickets_valid.csv
    │   ├── tickets_valid.json
    │   ├── tickets_valid.xml
    │   ├── tickets_malformed.csv
    │   ├── tickets_invalid_fields.json
    │   └── tickets_malformed.xml
    ├── test_ticket_api.test.ts
    ├── test_ticket_model.test.ts
    ├── test_import_csv.test.ts
    ├── test_import_json.test.ts
    ├── test_import_xml.test.ts
    ├── test_categorization.test.ts
    ├── test_integration.test.ts
    └── test_performance.test.ts
```

---

## Dependencies

**Runtime:** `express`, `zod`, `uuid`, `csv-parse`, `fast-xml-parser`, `multer`.
**Dev:** `typescript`, `@types/node`, `@types/express`, `@types/uuid`, `@types/multer`, `@types/supertest`, `ts-node-dev`, `jest`, `ts-jest`, `@types/jest`, `supertest`.

`tsconfig.json`: target ES2022, `strict: true`, `outDir: dist`, `rootDir: src`, `esModuleInterop: true`.
`jest.config.ts`: `preset: ts-jest`, `testEnvironment: node`, `collectCoverageFrom: ["src/**/*.ts", "!src/index.ts"]`, coverage thresholds set to `branches/functions/lines/statements: 85`.

---

## Task 1: Multi-Format Ticket Import API

### Data model — [src/models/ticket.schema.ts](src/models/ticket.schema.ts)

Zod schemas as the single source of truth (validation + TypeScript types via `z.infer`):

- `CategoryEnum`: `account_access | technical_issue | billing_question | feature_request | bug_report | other`
- `PriorityEnum`: `urgent | high | medium | low`
- `StatusEnum`: `new | in_progress | waiting_customer | resolved | closed`
- `SourceEnum`: `web_form | email | api | chat | phone`
- `DeviceEnum`: `desktop | mobile | tablet`
- `TicketCreateSchema`: required customer_id, customer_email (`.email()`), customer_name, subject (1–200), description (10–2000). Optional category/priority/status (defaults: `other`, `medium`, `new`), assigned_to, tags (string[]), metadata `{source, browser?, device_type?}`.
- `TicketUpdateSchema = TicketCreateSchema.partial()` plus `resolved_at`.
- Full `Ticket` type adds: `id` (uuid), `created_at`, `updated_at`, `resolved_at`, plus optional `classification` field for storing confidence/reasoning when auto-classified.

### Store — [src/store/ticketStore.ts](src/store/ticketStore.ts)

`Map<string, Ticket>` with: `create`, `getById`, `update` (patches `updated_at`, sets `resolved_at` if status→`resolved`), `delete`, `list({ category?, priority?, status?, assigned_to?, customer_id? })`, `clear()` (test helper).

### Routes — [src/routes/tickets.ts](src/routes/tickets.ts)

| Method | Path | Notes |
|---|---|---|
| POST | `/tickets` | Body validated by `TicketCreateSchema`. If `?autoClassify=true` (or body flag), run classifier and persist result. → 201 |
| POST | `/tickets/import` | `multer` memoryStorage single `file` field. Dispatch by `file.mimetype`/extension → CSV/JSON/XML importer. Returns `{ total, successful, failed: [{row, errors}] }`. → 200 with summary |
| GET | `/tickets` | Query filters mapped to `store.list`. → 200 |
| GET | `/tickets/:id` | 404 if missing |
| PUT | `/tickets/:id` | Validated by `TicketUpdateSchema` |
| DELETE | `/tickets/:id` | 204 |
| POST | `/tickets/:id/auto-classify` | Task 2 — runs classifier, applies result, returns ClassificationResult |

### Importers — [src/importers/](src/importers/)

Each importer returns `{ successful: Ticket[]; failed: { row: number; errors: string[] }[] }`.

- **csvImporter.ts** — `csv-parse/sync` with `columns: true, trim: true`. Parses `tags` as comma-delimited inside a cell; flattens `metadata.source`, `metadata.browser`, `metadata.device_type` from columns. Per-row Zod validation; collects errors instead of throwing.
- **jsonImporter.ts** — accepts top-level array or `{ tickets: [...] }`. Per-element Zod validation.
- **xmlImporter.ts** — `fast-xml-parser` (`ignoreAttributes: false`). Expect `<tickets><ticket>…</ticket></tickets>`. Normalizes single-vs-array shape; coerces `tags` from `<tag>` children. Per-element Zod validation.
- **index.ts** — `dispatch(buffer, mimetype, originalname)`; throws `HttpError(400, "unsupported format")` for unknown types; catches parser exceptions and returns `{ total: 0, successful: 0, failed: [{ row: 0, errors: ["malformed <fmt>: <msg>"] }] }`.

### Error handling — [src/middleware/errorHandler.ts](src/middleware/errorHandler.ts)

Central handler: Zod errors → 400 `{ error: "validation_error", details }`; `HttpError` → its status; otherwise 500. Multer errors (file too large, missing field) → 400.

---

## Task 2: Auto-Classification

### Rules — [src/classifier/rules.ts](src/classifier/rules.ts)

Two ordered keyword tables. Matching is **case-insensitive whole-word** (regex `\b…\b`) against `subject + " " + description`.

**Priority** (TASKS.md explicit list, evaluated top-down):
- `urgent`: `can't access`, `cannot access`, `critical`, `production down`, `security`
- `high`: `important`, `blocking`, `asap`
- `low`: `minor`, `cosmetic`, `suggestion`
- else: `medium`

**Category** (keyword sets per label; pick label with most matches; tie → first in declaration order; zero matches → `other`):
- `account_access`: login, log in, password, 2fa, mfa, locked out, sign in, reset password
- `technical_issue`: error, crash, freeze, broken, exception, stack trace, 500, timeout
- `billing_question`: invoice, payment, refund, charge, subscription, billing, receipt
- `feature_request`: feature request, please add, would love, suggestion, enhancement
- `bug_report`: bug, defect, reproduce, steps to reproduce, regression

### Classifier — [src/classifier/classifier.ts](src/classifier/classifier.ts)

`classify(ticket: Pick<Ticket,"subject"|"description">): ClassificationResult` where

```ts
type ClassificationResult = {
  category: Category;
  priority: Priority;
  confidence: number;        // 0..1
  reasoning: string;         // human-readable
  keywords_found: string[];  // every matched keyword across both axes
}
```

**Confidence formula** (simple, testable):
`confidence = min(1, 0.4 + 0.15 * keywords_found.length)` — base 0.4 (default category=other, priority=medium with zero matches gives 0.4), increasing with evidence; capped at 1.

**Reasoning** is a one-liner: `"Category '<x>' chosen due to keywords [a, b]; priority '<y>' due to [c]."` — falls back to `"No keywords matched; defaulted to other/medium."`.

### Endpoint and auto-run

- `POST /tickets/:id/auto-classify` — calls classifier, patches the stored ticket (`category`, `priority`, `classification`), logs the decision, returns the `ClassificationResult`.
- `POST /tickets` and `POST /tickets/import` accept `?autoClassify=true` (or `autoClassify: true` in JSON body) to run classification on creation. Manual `category`/`priority` values in the request **always win** — classifier only fills unset fields when auto-run, and the override is logged.
- **Log** — [src/classifier/log.ts](src/classifier/log.ts) keeps an in-memory array `{ ticket_id, at, result, manual_override?: boolean }`. Exposed via `getClassificationLog()` for tests (and could be a future GET endpoint).

---

## Task 3: AI-Generated Test Suite (Jest, >85%)

All API tests use `supertest(createApp())` against a fresh app instance; each suite calls `store.clear()` in `beforeEach`.

### [tests/test_ticket_api.test.ts](tests/test_ticket_api.test.ts) — 11 tests
1. POST creates ticket (201, returns UUID, timestamps set)
2. POST 400 on missing required field
3. POST 400 on invalid email
4. POST 400 on subject too long
5. GET `/tickets` returns empty array initially
6. GET filter by category returns subset
7. GET filter by priority+status combo
8. GET `/tickets/:id` 200 then 404 for unknown
9. PUT updates fields, bumps `updated_at`
10. PUT status→resolved sets `resolved_at`
11. DELETE returns 204 and subsequent GET is 404

### [tests/test_ticket_model.test.ts](tests/test_ticket_model.test.ts) — 9 tests
Zod validation: required fields; email format; subject min/max; description min/max; enum rejection for category/priority/status; tags must be array of strings; metadata.source enum; happy-path parse strips unknown keys; `TicketUpdateSchema` allows partial.

### [tests/test_import_csv.test.ts](tests/test_import_csv.test.ts) — 6 tests
Valid file → all imported; tag column comma-split; metadata columns map correctly; row with invalid email → in `failed`, valid rows still imported; malformed CSV (unbalanced quote) → graceful error in summary; empty file → `total: 0`.

### [tests/test_import_json.test.ts](tests/test_import_json.test.ts) — 5 tests
Top-level array; `{tickets: [...]}` shape; mixed valid+invalid records partitioned; invalid JSON syntax → graceful error; non-object element → row error.

### [tests/test_import_xml.test.ts](tests/test_import_xml.test.ts) — 5 tests
Standard `<tickets><ticket>…` parse; single `<ticket>` (non-array) normalization; `<tag>` children collected to array; malformed XML → graceful error; missing required field → in `failed`.

### [tests/test_categorization.test.ts](tests/test_categorization.test.ts) — 10 tests
Urgent priority keywords (3 separate tests: "can't access", "production down", "security"); high keyword ("blocking asap"); low keyword ("minor cosmetic"); default medium; category account_access ("password reset"); category billing_question ("refund my invoice"); category bug_report ("steps to reproduce"); confidence rises with more keywords; reasoning string contains matched keywords.

### [tests/test_integration.test.ts](tests/test_integration.test.ts) — 5 tests
End-to-end: (1) create → list → get → update → delete; (2) bulk-import CSV → list filters work on imported data; (3) bulk import with `autoClassify=true` — assert resulting category/priority on at least 3 imported tickets; (4) manual category survives auto-classify auto-run; (5) `POST /tickets/:id/auto-classify` overwrites category and persists confidence.

### [tests/test_performance.test.ts](tests/test_performance.test.ts) — 5 tests
Each uses `performance.now()` with generous CI-safe budgets:
1. Create 1000 tickets < 1500ms
2. List 1000 with filter < 200ms
3. Import 500-row CSV < 2000ms
4. Classify 1000 tickets < 1000ms
5. 50 concurrent GETs via `Promise.all` complete < 1500ms

### Fixtures — [tests/fixtures/](tests/fixtures/)

Small (5–10 row) hand-crafted files covering happy path + targeted malformed cases. The 50/20/30-row "sample data" deliverable files live separately under `demo/` and are not required for the test suite itself.

### Coverage

`jest --coverage` with `coverageThreshold` set to 85 for branches/functions/lines/statements in `jest.config.ts`. Run: `npm test -- --coverage`. Coverage exclusions: `src/index.ts` (just `.listen()`).

---

## Verification

1. **Install & build** — `npm install`, `npx tsc --noEmit` must pass.
2. **Run server** — `npm run dev` (ts-node-dev). Smoke-test with curl:
   - `curl -X POST localhost:3000/tickets -H "Content-Type: application/json" -d '{...}'` → 201
   - `curl -X POST localhost:3000/tickets/import -F "file=@tests/fixtures/tickets_valid.csv"` → summary JSON
   - `curl -X POST localhost:3000/tickets/<id>/auto-classify` → classification result
3. **Tests** — `npm test` (all suites green) and `npm test -- --coverage` (≥85% on each metric; threshold gate enforces this).
4. **Manual classifier sanity** — POST a ticket with subject "Production down — can't access account" and confirm `priority=urgent`, `category=account_access`, `confidence>0.7`, `keywords_found` includes both phrases.

---

## Out of scope (for this plan)

- Task 4 (multi-audience docs with Mermaid diagrams)
- Task 5 (extended integration + 20-concurrent-request perf tests beyond the 5 covered)
- Sample data deliverables (50 CSV / 20 JSON / 30 XML rows for `demo/`)
- Auth, persistence, rate limiting, OpenAPI generation