# Banking Transaction-Processing Pipeline Specification

> Ingest the information in this file, implement the Low-Level Tasks, and generate code that
> satisfies the High- and Mid-Level Objectives. This document is the input contract for Agent 2
> (the `code-generator` orchestrator), which routes each Low-Level Task below to a matching nested
> subagent (`transaction-validator`, `fraud-detector`, `compliance-agent`, `frontend-agent`) and
> builds the Integrator itself.

## High-Level Objective

A file-based multi-agent pipeline ingests raw banking transaction records, validates them,
scores them for fraud risk, applies a compliance decision, and writes an auditable, deterministic
final outcome for every transaction to `shared/results/`.
**Scope boundary**: this pipeline covers validation, fraud scoring, and compliance screening for
transactions already present in `sample-transactions.json`; it does not perform actual funds
settlement, ledger posting, live FX conversion, or real-time sanctions-list synchronization with a
third-party provider.

## Mid-Level Objectives

- **M1 — Structural & currency validation.** Every transaction is checked for required fields, a
  parseable decimal amount, and a valid ISO 4217 currency code before any downstream processing.
  Transactions that fail any check are written to `shared/results/` with a populated `reason`
  field and never reach the fraud detector.
  *Verification: unit tests over sample rows TXN001–TXN008 plus synthetic missing-field fixtures;
  `--dry-run` count report.*
- **M2 — Fraud risk scoring.** Every validated transaction receives a deterministic 0–100 risk
  score from three documented signals — value ≥ $10,000, off-hours timing, cross-border indicator
  — and transactions scoring ≥ 50 are flagged `fraud_review=true`. The boundary amount $9,999.99
  (TXN003) never triggers the high-value signal.
  *Verification: table-driven unit tests asserting exact score per fixture, run twice for
  determinism.*
- **M3 — Compliance decision & regulatory reporting.** Every scored transaction receives a final
  decision (`cleared` / `flagged` / `rejected`) with reason(s), a `requires_report` flag for
  amounts at or above the $10,000 reporting threshold, and blocked-account / missing-regulated-
  field screening; the decision is written idempotently to `shared/results/`.
  *Verification: unit tests per rule + a reconciliation check that every result file has a
  decision in the closed set `{cleared, flagged, rejected}`.*
- **M4 — End-to-end auditability.** Every operation performed by every agent (validator, fraud
  detector, compliance checker, integrator) produces an append-only audit-log entry containing an
  ISO 8601 timestamp, agent name, transaction ID, and outcome; account numbers are masked
  (last 4 digits only) and no full name is ever written to a log line.
  *Verification: log-format regex assertions + an automated PII-pattern scan of captured log
  output; sign-off by a manual compliance spot-check of a sample log excerpt.*
- **M5 — Pipeline completeness & observability.** Running the integrator against
  `sample-transactions.json` drives all 8 sample transactions to a terminal state in
  `shared/results/` (including deterministic, non-duplicating handling of a repeated
  `transaction_id`), produces a pipeline summary report, and the frontend's `/api/status` endpoint
  reflects each transaction's current lifecycle stage within the read-after-write consistency
  target defined in Performance Targets.
  *Verification: an isolated-filesystem integration test asserting 8/8 terminal outcomes and a
  second run proving idempotency; manual UI walkthrough of the lifecycle timeline.*

## Implementation Notes

- **Language/runtime**: Python 3.11+, type-hinted, `pytest` + `pytest-cov` for tests.
- **Money**: every amount is parsed and compared as `decimal.Decimal` — **never `float`**. Amounts
  are quantized to the currency's ISO 4217 minor unit (2 decimal places for USD/EUR/GBP, 0 for
  JPY, etc.) using `ROUND_HALF_EVEN`. A currency-to-minor-unit lookup table is a named constant,
  not inline magic numbers.
- **Currency**: validated against a static ISO 4217 alphabetic-code table (USD, EUR, GBP, JPY, and
  the other active codes). Unknown codes (e.g. `XYZ`) are rejected at the validator with a
  `reason`; no downstream agent re-validates currency.
- **Audit trail**: every agent operation logs, at minimum, `{timestamp: ISO 8601 UTC, agent_name,
  transaction_id, outcome}`. Logs are append-only (no in-place edits). Account numbers are masked
  as `ACC-***####` (last 4 digits visible only); no `name`-type field from any future data source
  is ever logged in plaintext. No raw request/response payload containing an unmasked account
  number is written to any log file.
- **File-based message protocol** (per `TASKS.md` Task 2): agents communicate exclusively through
  JSON files under `shared/{input,processing,output,results}/`. Standard message shape:
  `message_id` (uuid4), `timestamp` (ISO 8601), `source_agent`, `target_agent`, `message_type`,
  `data` (transaction payload + accumulated stage results). Writes are **atomic**: an agent writes
  to a temp file in the target directory and renames it into place, so no downstream reader (agent
  or frontend) ever observes a partially written file.
- **Idempotency**: before processing an incoming message, an agent checks whether a result for
  that `transaction_id` already exists in `shared/results/`. If it does, the agent returns the
  existing outcome unchanged and logs a single `duplicate_ignored` audit entry — it never
  recomputes, re-scores, or double-writes.
- **Fail-closed default**: on any ambiguous input, parse failure, or write failure, the safe
  outcome is `rejected` (validator) or `flagged`/held (compliance/integrator) — never a silent
  `cleared`.
- **Configuration over hardcoding**: the blocked-account list and any fraud-score weights are
  stored in a versioned config file (e.g. `agents/config/blocked_accounts.json`,
  `agents/config/fraud_rules.json`), not embedded as inline literals in agent code, so ops/
  compliance can update them without a code change.
- **No live external dependencies in v1**: no FX-rate service and no third-party sanctions API are
  assumed available; both are explicitly out of scope (see High-Level Objective scope boundary)
  and any threshold comparison across currencies is documented as a stated assumption rather than
  silently approximated.

## Context

### Beginning context
- `sample-transactions.json` exists at the `homework-6/` root with 8 raw transaction records
  (`TXN001`–`TXN008`), including the edge cases enumerated below.
- `shared/` does not yet exist; it is created by the integrator on first run.
- No `agents/`, `frontend/`, or `tests/` directories exist yet.
- No audit log, no `shared/results/` content, no summary report.

### Ending context
- `shared/{input,processing,output,results}/` exist and are populated over the course of a run.
- `shared/results/` contains exactly one final-outcome JSON file per `transaction_id`
  (`TXN001.json` … `TXN008.json`), each carrying `status`/`decision`, `reason`(s), fraud
  `risk_score`, `fraud_review` flag, and `requires_report` flag.
- A pipeline summary report (e.g. `shared/results/summary.json`) aggregates counts: total
  processed, validated, rejected-at-validation, flagged, cleared, rejected-at-compliance,
  requires-report count.
- An audit log file (e.g. `logs/audit.log`) contains one line per agent operation, matching the
  format in Implementation Notes.
- `agents/transaction_validator.py`, `agents/fraud_detector.py`, `agents/compliance_checker.py`,
  `integrator.py`, `frontend/server.py`, `frontend/static/index.html` all exist and are runnable.
- `tests/` contains unit tests per agent plus one integration test; `pytest --cov` reports
  **≥ 90%** statement coverage (the coverage-gate hook in Task 3 blocks push below 80%).
- The frontend is reachable (e.g. `uvicorn frontend.server:app`) and shows each of the 8 sample
  transactions moving through input → processing → validated → scored → compliance → results.

## Low-Level Tasks

### Task: Transaction Validator (serves: M1)
```
Task: Transaction Validator (serves: M1)
Prompt: "Create agents/transaction_validator.py for the banking pipeline described in
homework-6/specification.md and homework-6/TASKS.md (Task 2). Implement
process_message(message: dict) -> dict that reads a standard-shape transaction message, validates
required fields (transaction_id, amount, currency, source_account, destination_account,
timestamp), parses amount as decimal.Decimal (reject non-numeric/malformed values), validates
currency against ISO 4217, and applies the negative-amount rule: negative amounts are permitted
only when transaction_type == 'refund' (store the absolute value as the canonical amount and set
data.direction = 'refund_credit'); a negative amount on any other transaction_type is rejected
with reason 'negative_amount_not_permitted'. On success, write the message to shared/output/ for
the fraud detector with status='validated'. On failure, write directly to shared/results/ with
status='rejected' and a populated reason field, bypassing fraud/compliance. Support a --dry-run
CLI flag that validates sample-transactions.json without moving files and prints total/valid/
invalid counts and rejection reasons. Reuse the shared message-protocol helper for message shape,
atomic file moves, decimal parsing, audit logging, and idempotency checks (skip reprocessing if a
result already exists for the transaction_id). Add ISO 8601 audit log lines (timestamp, agent
name 'transaction_validator', transaction_id, outcome) with account numbers masked to last 4
digits. Write unit tests in tests/test_transaction_validator.py covering TXN001, TXN003, TXN006,
TXN007, a missing-field fixture, and a duplicate-transaction_id fixture."
File to CREATE: agents/transaction_validator.py
Function to CREATE: process_message(message: dict) -> dict
Details: Checks (in order): required-field presence; decimal-parseable amount; ISO 4217 currency
membership; negative-amount-vs-refund rule. Emits a reason string identifying exactly which check
failed (e.g. "invalid_currency_code:XYZ", "missing_required_field:amount",
"negative_amount_not_permitted"). Never mutates the incoming message's transaction_id. Idempotent:
re-running on an already-resulted transaction_id returns the stored outcome and logs
"duplicate_ignored" without rewriting shared/results/.
Acceptance Criteria:
- [ ] TXN006 (currency XYZ) rejected with reason containing "invalid_currency" and lands in
      shared/results/ without ever appearing in shared/output/.
- [ ] TXN007 (-100.00 GBP refund) is accepted; canonical amount is Decimal("100.00") with
      direction="refund_credit" recorded in the outgoing message.
- [ ] A synthetic negative-amount, non-refund fixture is rejected with reason
      "negative_amount_not_permitted".
- [ ] `--dry-run` against sample-transactions.json reports 8 total transactions with a valid/
      invalid split matching the edge-case table below.
- [ ] Re-submitting an already-processed transaction_id produces zero duplicate result files.
```

### Task: Fraud Detector (serves: M2)
```
Task: Fraud Detector (serves: M2)
Prompt: "Create agents/fraud_detector.py for the banking pipeline described in
homework-6/specification.md. Implement process_message(message: dict) -> dict that reads a
validated message from shared/output/, computes a deterministic risk score in [0, 100] from three
signals: +50 if amount >= Decimal('10000.00') in the transaction's stated currency (no live FX
conversion — documented assumption), +20 if the transaction timestamp's UTC hour is in [0, 6)
(off-hours), +15 if metadata.country is not in the configured home-country set (default {'US'},
cross-border signal). Sum the signals into risk_score; set fraud_review=true only when
risk_score >= 50, else false (fraud remains a signal, not a hard reject, for 25-49). Attach
risk_score, fraud_review, and the list of triggered signal names to the outgoing message, then
write it to shared/output/ for the compliance checker. Reuse the shared message-protocol helper
for decimal parsing, atomic moves, audit logging, and idempotency. Write ISO 8601 audit log lines
(agent name 'fraud_detector', transaction_id, risk_score, fraud_review) with account numbers
masked. Write unit tests in tests/test_fraud_detector.py that are table-driven over TXN001-TXN005,
TXN007, TXN008 fixtures and assert the exact score, re-running each fixture twice to prove
determinism."
File to CREATE: agents/fraud_detector.py
Function to CREATE: process_message(message: dict) -> dict
Details: Threshold, off-hours window, and cross-border home-country set are named constants
sourced from agents/config/fraud_rules.json, not inline literals. Score computation must be pure
(no I/O side effects) so it is independently unit-testable; the process_message wrapper handles
file I/O and audit logging around the pure scoring function.
Acceptance Criteria:
- [ ] TXN002 ($25,000 USD) and TXN005 ($75,000 USD) each score >= 50 and fraud_review=true.
- [ ] TXN003 ($9,999.99 USD) scores 0 on the high-value signal specifically (boundary respected).
- [ ] TXN004 (02:47 UTC, DE) scores exactly 35 (off-hours +20, cross-border +15) and
      fraud_review=false (signal recorded, not hard-flagged).
- [ ] Calling process_message twice on an identical input produces an identical risk_score.
```

### Task: Compliance Checker (serves: M3)
```
Task: Compliance Checker (serves: M3)
Prompt: "Create agents/compliance_checker.py for the banking pipeline described in
homework-6/specification.md — the required third cooperating agent and final decision stage.
Implement process_message(message: dict) -> dict that reads a scored message from shared/output/
and applies three rules: (1) requires_report=true when amount >= Decimal('10000.00') in the
transaction's currency, reason 'regulatory_reporting_threshold'; (2) reject with reason
'blocked_account' if source_account or destination_account appears in
agents/config/blocked_accounts.json (a synthetic test list that must NOT include any account
number from sample-transactions.json, to keep sample-data behavior independent of the blocklist
fixture); (3) reject with reason 'missing_regulated_field:<field>' if the transaction is
cross-border (metadata.country outside the configured home-country set) or transaction_type ==
'wire_transfer' and metadata.channel or description is empty. Compute the final decision: 'rejected'
if rule 2 or 3 triggers; else 'flagged' if fraud_review is true OR requires_report is true; else
'cleared'. Write the final message (decision, reason list, requires_report, risk_score,
fraud_review) to shared/results/ using an atomic write keyed by transaction_id, fail-closed on any
screening error (default to 'flagged', never silently 'cleared'). Reuse the shared
message-protocol helper for decimal parsing, atomic moves, audit logging, idempotency. Write ISO
8601 audit log lines (agent name 'compliance_checker', transaction_id, decision, reason) with
account numbers masked. Write unit tests in tests/test_compliance_checker.py covering a blocked-
account fixture, a missing-regulated-field fixture, and TXN001-TXN008 outcomes."
File to CREATE: agents/compliance_checker.py
Function to CREATE: process_message(message: dict) -> dict
Details: Decision is always one of the closed set {cleared, flagged, rejected} — no other string
value is ever written. On an internal screening exception, catch it, log the exception class name
(not the raw account data) at audit level, and return decision='flagged' with reason
'compliance_screening_error'.
Acceptance Criteria:
- [ ] TXN002 and TXN005 land in shared/results/ with decision='flagged', requires_report=true.
- [ ] TXN003 lands with requires_report=false (boundary respected end-to-end).
- [ ] A synthetic blocked-account fixture (not overlapping sample-transactions.json) is rejected
      with reason 'blocked_account'.
- [ ] Every record in shared/results/ after a full sample run has decision in
      {cleared, flagged, rejected} — verified by a reconciliation test.
```

### Task: Integrator / Orchestrator (serves: M5)
```
Task: Integrator / Orchestrator (serves: M5)
Prompt: "Create integrator.py at the homework-6 project root. Implement
run_pipeline(sample_file: str = 'sample-transactions.json') -> dict plus a main() CLI entrypoint.
run_pipeline must: create shared/{input,processing,output,results}/ if absent; load every record
from sample_file, wrap each in the standard message shape (message_id, timestamp, source_agent=
'integrator', target_agent='transaction_validator', message_type='transaction', data=<record>),
and write each as an atomic JSON file into shared/input/; invoke the validator, then the fraud
detector, then the compliance checker in that order for each transaction (in-process function
calls or subprocess invocation, either is acceptable, but the ORDER must be validator -> fraud
detector -> compliance checker); poll/monitor shared/results/ until every transaction_id from the
input batch has a terminal result or a configurable timeout (assumed 30s for 8 records) elapses;
write a pipeline summary report to shared/results/summary.json aggregating total/validated/
rejected-at-validation/flagged/cleared/rejected-at-compliance/requires-report counts; print the
summary to stdout. On a malformed or unreadable record in sample_file, skip that record, write a
synthetic rejected result with reason 'malformed_input', continue processing the remaining
records, and report the parse-error count separately in the summary — never abort the whole
batch. Emit an ISO 8601 audit log line for pipeline start/end (agent name 'integrator')."
File to CREATE: integrator.py
Function to CREATE: run_pipeline(sample_file: str = "sample-transactions.json") -> dict
Details: run_pipeline must be callable from the integration test with an injected shared/ root
(e.g. via a parameter or environment variable) so tests never touch the project's real shared/
tree. Idempotent: calling run_pipeline twice on the same sample_file produces the same 8 result
files with no duplicates in shared/results/ (the second run's per-transaction outcomes are read
from existing results, not recomputed).
Acceptance Criteria:
- [ ] After one run, shared/results/ contains exactly 8 files, one per TXN001-TXN008, each with a
      terminal decision/status.
- [ ] shared/results/summary.json exists and its counts sum to 8.
- [ ] Running run_pipeline a second time against the same sample_file does not create duplicate
      result files or change any existing decision.
- [ ] A sample_file containing one syntactically invalid JSON record still yields results for all
      remaining valid records plus one 'malformed_input' entry.
```

### Task: Frontend / Web UI (serves: M5)
```
Task: Frontend / Web UI (serves: M5)
Prompt: "Build frontend/server.py (FastAPI) and frontend/static/index.html for the banking
pipeline described in homework-6/specification.md. The server must expose: GET / serving the
static page; POST /submit that drops selected (or all) sample-transactions.json records into
shared/input/ as standard-shape messages, reusing integrator.py's message construction so the
running pipeline picks them up; GET /api/status returning a JSON array with one entry per
transaction_id describing its current stage (input/processing/validated/scored/compliance/
results), validation status, fraud risk_score and fraud_review, compliance decision and reason,
and last-updated timestamp — read ONLY from shared/{input,processing,output,results}/, never by
re-running agent logic, and with account numbers masked to last 4 digits in every response. The
index.html page must include a 'Submit sample transactions' control and poll /api/status on an
interval (or use SSE) to render a per-transaction lifecycle timeline that updates live and is
color/label-coded by outcome (cleared/flagged/rejected)."
File to CREATE: frontend/server.py
File to CREATE: frontend/static/index.html
Details: The UI is a read-only observer plus an injector — it must not implement or duplicate
validator/fraud/compliance logic. No plaintext account number or name appears in any HTTP response
body or rendered page. Keep the frontend dependency-free beyond FastAPI + vanilla JS/fetch (no
build step required).
Acceptance Criteria:
- [ ] Starting `uvicorn frontend.server:app` and calling POST /submit places all 8 sample
      transactions into shared/input/.
- [ ] GET /api/status returns 8 entries, each progressing from "input" to a terminal stage as the
      pipeline (started separately or by /submit) processes them.
- [ ] No response body from any endpoint contains an unmasked account number.
- [ ] The rendered page visibly updates a transaction's row as its stage changes, without a full
      page reload.
```

## Edge Cases & Failure Modes

| # | Scenario | Sample Data | Expected Behavior (visible outcome) | Audit / Compliance Implication |
|---|---|---|---|---|
| 1 | Invalid ISO 4217 currency code | TXN006, currency `XYZ` | Validator rejects immediately; record written to `shared/results/` with `status='rejected'`, `reason='invalid_currency_code:XYZ'`; never reaches fraud/compliance | Audit line from `transaction_validator`, `outcome='rejected'`; excluded from `requires_report` accounting |
| 2 | Negative amount on a refund | TXN007, `amount='-100.00'`, `transaction_type='refund'` | Accepted; validator stores canonical `amount=Decimal('100.00')` and `direction='refund_credit'`; proceeds normally through fraud/compliance | Audit shows `outcome='validated'` with the sign normalization noted in the message payload, not silently dropped |
| 3 | Negative amount on a non-refund type | Synthetic fixture (not in sample data) | Rejected, `reason='negative_amount_not_permitted'` | Audit `outcome='rejected'`; documents the fail-closed default for an otherwise-ambiguous sign |
| 4 | Off-hours timing | TXN004, `02:47:00Z` | Not rejected; fraud detector adds the off-hours signal (+20) to `risk_score`; transaction continues to compliance carrying the signal | Audit/compliance record shows the signal and score but decision remains `cleared` unless another rule pushes it to `flagged`/`rejected` |
| 5 | High-value wire transfer | TXN002 ($25,000 USD), TXN005 ($75,000 USD) | Fraud detector scores >= 50, `fraud_review=true`; compliance sets `requires_report=true`; final decision `flagged` (pending manual review), never auto-`cleared` | Audit trail carries `risk_score`, `requires_report`, and the reporting reason for regulator-facing reconciliation |
| 6 | Boundary amount just under the $10k rule | TXN003, `amount='9999.99'` | High-value signal (+50) does NOT trigger (strict `>=` comparison); `requires_report=false`; likely `cleared` absent other signals | Audit shows `risk_score` excludes the high-value component; used as the canonical boundary regression fixture |
| 7 | Missing required field | Synthetic fixture (e.g. `amount` omitted) | Validator rejects, `reason='missing_required_field:amount'`; written to `shared/results/` | Audit `outcome='rejected'`; fail-closed — never proceeds with a null/assumed value |
| 8 | Duplicate `transaction_id` | Any TXN re-submitted twice (e.g. re-run of `run_pipeline` or a re-POST via `/submit`) | Agent detects an existing `shared/results/<id>.json`; returns the stored outcome unchanged; no reprocessing, no duplicate file, no double-count in the summary | Audit logs a single `outcome='duplicate_ignored'` line referencing the original decision; summary counts stay stable across re-runs |
| 9 | Unreadable / partial JSON | A malformed record injected into `sample-transactions.json` or a corrupted `shared/` message file | Integrator/agent skips the single bad record, writes a synthetic `status='rejected'`, `reason='malformed_input'` result, and continues processing the remaining batch — the whole run never aborts | Audit logs `outcome='rejected'` with a `parse_error=true` marker; the pipeline summary reports a distinct `malformed_input_count` |
| 10 | Audit-write / results-write failure | Simulated disk-full or permission-denied on `shared/results/` or the audit log path | The transaction is never reported as `cleared`; the agent retries the write (assumed 3 attempts) then marks the transaction `status='error'` (held for manual ops review) rather than dropping it silently | A best-effort fallback log entry is written to a secondary local error log so ops can reconcile held transactions; `run_pipeline`'s summary surfaces an `error_count` distinct from `rejected_count` |

## Verification & Test Strategy

- **M1 (validation).** `tests/test_transaction_validator.py`: fixtures derived directly from
  TXN001, TXN003, TXN006, TXN007, plus two synthetic fixtures (missing field, non-refund negative
  amount). Assert rejected records appear in an isolated `shared/results/` (via `tmp_path`) with a
  non-empty `reason`. `--dry-run` output is asserted against the exact expected valid/invalid
  split for all 8 sample rows.
- **M2 (fraud scoring).** `tests/test_fraud_detector.py`: table-driven test asserting the exact
  `risk_score` and `fraud_review` for TXN001–TXN005, TXN007, TXN008. Each fixture is scored twice
  in the same test to assert determinism (identical input → identical output).
- **M3 (compliance).** `tests/test_compliance_checker.py`: one fixture per rule (reporting
  threshold, blocked account — using a synthetic account not present in sample data, missing
  regulated field), plus a reconciliation assertion that iterates every file the full sample run
  produces in `shared/results/` and checks `decision in {cleared, flagged, rejected}`.
- **M4 (auditability).** A log-capture test asserts every emitted audit line matches an ISO 8601
  timestamp regex, an agent name from the closed set `{transaction_validator, fraud_detector,
  compliance_checker, integrator}`, a `transaction_id`, and an `outcome`. A separate PII-pattern
  scan asserts no captured log line contains an unmasked account number (regex for a full
  `ACC-####` pattern outside the `***`-masked form) or a `name` field. A manual compliance
  spot-check of one sample log excerpt is recorded as a sign-off step, not a substitute for the
  automated scan.
- **M5 (completeness/observability).** `tests/test_integration_pipeline.py`: runs `run_pipeline`
  against `sample-transactions.json` in an isolated `tmp_path` shared/ root; asserts all 8
  `transaction_id`s appear exactly once in `shared/results/`; re-invokes `run_pipeline` a second
  time and asserts zero new/changed result files (idempotency); asserts `summary.json` counts sum
  to 8. A manual QA pass starts the frontend, calls `/submit`, and visually confirms the lifecycle
  timeline advances for each transaction to a terminal state.
- **Coverage.** `pytest --cov=agents --cov=frontend --cov=integrator` must report **≥ 90%**
  statement coverage; the Task 3 coverage-gate hook independently blocks any push below 80%.

## Performance Targets (assumed)

All figures below are **assumed targets** for a homework-scale, single-process, local-filesystem
pipeline (no network calls, no external FX/sanctions services) — they are sized to be
comfortably achievable on typical development hardware while still being falsifiable in a test.

- **Per-transaction processing latency**: validator + fraud detector + compliance checker combined
  complete in **≤ 200 ms p95** for one transaction. *Justification: each stage performs in-memory
  `Decimal`/dict operations and a small number of local file writes with no network round-trip, so
  sub-200ms leaves generous headroom versus typical CI-machine I/O variance.*
- **Batch throughput**: the full 8-record `sample-transactions.json` completes end-to-end
  (`run_pipeline`) in **≤ 2 seconds**. *Justification: ~15x the per-transaction p95 budget,
  accounting for directory creation, polling overhead, and summary aggregation.*
- **Sustained validator throughput**: `--dry-run` mode processes **≥ 25 transactions/second**
  single-process. *Justification: dry-run performs no file I/O beyond reading the source JSON
  once, so it is bound only by field/regex/decimal-parse cost.*
- **Batch size ceiling**: the pipeline is designed to accept batches up to **10,000 transactions**
  per `run_pipeline` invocation without exceeding `O(n)` memory or directory-scan cost.
  *Justification: this bounds the implementation away from `O(n²)` result-directory scans, which
  is the most likely accidental performance regression in a naive file-polling design.*
- **Read-after-write consistency**: the frontend's `GET /api/status` reflects a transaction's new
  stage within **≤ 1 second** of the corresponding `shared/` file write. *Justification: this is a
  same-machine local filesystem poll with no distributed replication, so a 1-second poll interval
  is both achievable and sufficient for a human-observable "real-time" dashboard.*

## Assumptions & Open Questions

- No live FX-rate feed exists; the $10,000 fraud/reporting threshold is compared directly against
  the transaction's stated-currency amount without conversion. This is acceptable for the given
  sample data (large amounts are all USD) but must be revisited before handling large non-USD
  transactions in production.
- The institution's "home country" for cross-border scoring is assumed to be `{"US"}`, configurable
  via `agents/config/fraud_rules.json`.
- The blocked-account list used for compliance testing is a synthetic fixture that intentionally
  does not overlap any account number in `sample-transactions.json`, so sample-data behavior stays
  independent of the blocklist's specific contents.
- Off-hours is defined as UTC hour `< 6`; this is a simplification that does not account for the
  account holder's local timezone and is documented as a v1 limitation.
