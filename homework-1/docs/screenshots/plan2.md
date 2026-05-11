## Task 4 (Options A, B, D) — Detailed Implementation Plan

### Summary
Extend the existing Node.js + Express banking API with three additional features from Task 4:

1. `GET /accounts/:accountId/summary` (Option A)  
2. `GET /accounts/:accountId/interest?rate=...&days=...` (Option B)  
3. Global rate limiting: max `100` requests per minute per IP (Option D)  

Add dedicated automated tests for each option and update `README.md` to document new endpoints, behavior, and validation rules.

### API and Behavior Changes
- Add a reusable account ledger computation helper used by `balance`, `summary`, and `interest` to avoid duplicated business logic.
- Keep account ID validation consistent with existing pattern (`ACC-XXXXX`) and existing error format.

- `GET /accounts/:accountId/summary`
  - Validates `accountId`.
  - Computes account-centric cashflow:
    - `totalDeposits`: inflows to account (`deposit` toAccount + incoming `transfer`)
    - `totalWithdrawals`: outflows from account (`withdrawal` fromAccount + outgoing `transfer`)
  - `transactionCount`: number of related transactions (any role in from/to).
  - `mostRecentTransactionDate`: latest related transaction timestamp or `null` if none.
  - Returns `200` with summary payload for both populated and empty accounts.

- `GET /accounts/:accountId/interest?rate=0.05&days=30`
  - Validates `accountId`, `rate`, and `days`.
  - Validation rules:
    - `rate` is required, numeric, and `>= 0`
    - `days` is required, numeric integer, and `>= 0`
  - Uses current balance (can be negative) and simple interest:
    - `interest = balance * rate * (days / 365)`
  - Returns `200` with account id, principal (current balance), inputs, and computed interest (rounded consistently to 2 decimals for currency-like output).
  - For empty accounts, returns `200` with zero balance and zero interest.

- Global rate limiting (Option D)
  - Apply middleware at app level so all API routes are covered.
  - Limit: `100` requests per `60` seconds per IP.
  - On limit exceed, return `429` JSON error payload (consistent with existing API style, e.g. `{ error: "Too many requests" }`).

### Implementation Changes
- Routing/service layer
  - Extend accounts routes in existing router to add `summary` and `interest`.
  - Extract shared ledger/account analytics helper (balance, inflow/outflow, related tx list, most recent date) so all account endpoints use one source of truth.

- Validation layer
  - Add query validator for interest parameters (`rate`, `days`) with field-level details.
  - Reuse existing validation response structure for bad requests.

- Middleware
  - Add rate-limiter dependency and app-level middleware registration before routes.
  - Configure JSON error response for 429.

- Documentation
  - Update README sections:
    - Implemented features list now includes Task 4 A/B/D.
    - Endpoint table includes new summary and interest endpoints.
    - Add interest formula and parameter constraints.
    - Add rate limit behavior (`100 req/min/IP`, HTTP 429).
    - Update testing section to include new test groups.

### Test Plan
- Option A: summary endpoint
  - Returns correct deposits/withdrawals/count/mostRecent for mixed `deposit`, `withdrawal`, `transfer`.
  - Correctly includes transfer inflow/outflow in totals.
  - Returns `200` with zero totals and `mostRecentTransactionDate: null` when no related transactions.
  - Returns `400` for invalid account format.

- Option B: interest endpoint
  - Computes interest correctly for positive balance.
  - Computes negative interest correctly for negative balance.
  - Returns zero interest for empty account (zero balance).
  - Returns `400` for invalid `rate`/`days` (missing, non-numeric, negative, non-integer days).

- Option D: rate limiting
  - Allows requests under the threshold.
  - Returns `429` after exceeding 100 requests from same IP in test window.
  - Verifies limiter applies to existing endpoints and new endpoints (global scope).

- Regression coverage
  - Keep existing Task 1–3 tests intact.
  - Ensure no behavior regressions in transaction creation/filtering/balance endpoint.

### Assumptions and Defaults
- Summary totals are account cashflow totals (inflow/outflow), not strict transaction-type-only counters.
- Interest uses raw current balance (including negative values) and simple interest formula with `days/365`.
- Empty accounts are valid and return `200` with zero/null summary/interest fields.
- Rate limiting is global across all routes by client IP.
- Existing in-memory storage model remains unchanged (no database, state resets on restart).
