# Verified Research: Bug 001 — ledger CLI (BUG-001, BUG-002, SEC-001)

## Verification Summary
- **Result:** PASS
- **Research Quality:** L4 — 🟢 Good   (per research-quality-measurement skill)
- **Claims:** 23/25 verified (1 partial, 1 false, 0 unverifiable)
- **Verified by / date:** Bug Research Verifier — 2026-06-24

All three buggy locations and all three root-cause diagnoses (the critical
claims) were independently confirmed against the real source. Two minor,
non-critical discrepancies were found and are documented below.

## Verified Claims
| # | Claim | Reference (file:line) | Status | Note |
|---|-------|-----------------------|--------|------|
| 1 | BUG-001 located in `average`, division-by-zero, no empty-array guard | src/calc.js:30 | ✅ | Critical. Line 30 is `return sum(numbers) / numbers.length;`. |
| 2 | `average` declared here | src/calc.js:29 | ✅ | `function average(numbers) {`. |
| 3 | Verbatim snippet of `average` (lines 29–31) | src/calc.js:29-31 | ✅ | Character-for-character match. |
| 4 | `sum` returns 0 for `[]`, declared at lines 16–18 | src/calc.js:16-18 | ✅ | `numbers.reduce((total, n) => total + n, 0)`. |
| 5 | `avg` command calls `average` | src/index.js:39 | ✅ | `return average(toNumbers(args));`. |
| 6 | BUG-001 failing test snippet | tests/calc.test.js:20-23 | ✅ | Critical. `assert.equal(average([]), 0);` matches exactly. |
| 7 | BUG-002 located in `applyDiscount`, subtracts percent as flat amount | src/calc.js:44 | ✅ | Critical. Line 44 is `return price - percent;`. |
| 8 | `applyDiscount` declared here | src/calc.js:43 | ✅ | `function applyDiscount(price, percent) {`. |
| 9 | Verbatim snippet of `applyDiscount` (lines 43–45) | src/calc.js:43-45 | ✅ | Character-for-character match. |
| 10 | `discount` command block calls `applyDiscount` | src/index.js:40-43 | ✅ | `case 'discount'` block; `return applyDiscount(price, percent);`. |
| 11 | Diagnosis: `applyDiscount(200,10)` returns 190, should be 180 | src/calc.js:44 | ✅ | Critical. Logic confirmed (`200 - 10 = 190`). |
| 12 | BUG-002 failing test snippet | tests/calc.test.js:25-28 | ✅ | Critical. `assert.equal(applyDiscount(200, 10), 180);` matches exactly. |
| 13 | SEC-001 located in `evaluateExpression`, eval injection (CWE-95) | src/evaluate.js:23 | ✅ | Critical. Line 23 is `return eval(expr); // eslint-disable-line no-eval`. |
| 14 | `evaluateExpression` declared here | src/evaluate.js:22 | ✅ | `function evaluateExpression(expr) {`. |
| 15 | Verbatim snippet of `evaluateExpression` (lines 22–24) | src/evaluate.js:22-24 | ✅ | Character-for-character match. |
| 16 | `calc` command passes CLI input to `evaluateExpression` | src/index.js:45 | ✅ | `return evaluateExpression(args.join(' '));` (snippet also quotes the `case 'calc':` label at line 44, matches). |
| 17 | Raw CLI string originates from `process.argv.slice(2)` | src/index.js:52 | ⚠️ | Line 52 assigns to `argv`, not `args` (see Discrepancies). Data-flow conclusion correct. |
| 18 | Benign-only test snippet for `evaluateExpression` | tests/evaluate.test.js:14-16 | ✅ | Critical (test-coverage claim). `assert.equal(evaluateExpression('2 + 3'), 5);` matches exactly. |
| 19 | Comment anticipates a "rejects non-numeric input" test | tests/evaluate.test.js:8-12 | ✅ | Comment present; lines 11–12 reference the future regression test. |
| 20 | Expected `npm test`: "2 failing, 2 passing" | tests/calc.test.js, tests/evaluate.test.js | ❌ | Actual is 2 failing / **3** passing (see Discrepancies). |
| 21 | `src/calc.js` is 47 lines + trailing newline | src/calc.js:47 | ✅ | File ends at line 47 (`module.exports`) + newline. |
| 22 | `src/evaluate.js` is 26 lines + trailing newline | src/evaluate.js:26 | ✅ | File ends at line 26 + newline. |
| 23 | `src/index.js` calc dispatch line 45, argv slice line 52, avg line 39, discount 40–43 | src/index.js | ✅ | All four line references confirmed. |
| 24 | No source files were modified during research | src/, tests/ | ✅ | Files read are in the intended "before"/buggy state; no fix applied. |
| 25 | SEC-001 surfaces only as static finding, not a failing test | tests/evaluate.test.js | ✅ | Only benign input tested; suite stays green for this file. |

## Discrepancies Found

1. **Test-count claim is wrong (Claim #20) — ❌ False, non-critical.**
   - **Research says:** Summary line — "Expected `npm test` result in the current 'before' state: **2 failing, 2 passing**."
   - **Source actually shows:** Five tests total. `tests/calc.test.js` has four
     (`sum adds a list of numbers` ✅, `average of a non-empty list` ✅,
     `average of an empty list is 0 (BUG-001)` ❌, `applyDiscount applies a
     percentage (BUG-002)` ❌); `tests/evaluate.test.js` has one
     (`evaluateExpression computes a simple arithmetic expression` ✅). That is
     **2 failing, 3 passing**, not 2 passing.
   - **Impact:** Minor. The failing count (2) and the two failing tests are
     correct; only the passing tally is off by one (it omits one of the three
     passing tests). Does not affect any bug location or fix.

2. **Variable-name imprecision in SEC-001 data flow (Claim #17) — ⚠️ Partial, non-critical.**
   - **Research says:** "`src/index.js:52` builds `args` from
     `process.argv.slice(2)`, so the raw command-line string reaches `eval()`
     unchanged."
   - **Source actually shows:** `src/index.js:52` is
     `const argv = process.argv.slice(2);` — it builds **`argv`**, not `args`.
     The `args` array is destructured later at `src/index.js:33`
     (`const [command, ...args] = argv;`).
   - **Impact:** Minor naming imprecision. The underlying claim — that untrusted
     `process.argv` input flows unchanged into `eval()` via the `calc` command —
     is correct.

## Research Quality Assessment
- **Level:** L4 — 🟢 Good
- **Verification rate:** 23/25 = 92%
- **Critical claims:**
  - BUG-001 location `src/calc.js:30` + diagnosis (division by zero → `NaN`) — ✅ Verified.
  - BUG-002 location `src/calc.js:44` + diagnosis (flat subtraction vs. percentage) — ✅ Verified.
  - SEC-001 location `src/evaluate.js:23` + diagnosis (eval injection, CWE-95) — ✅ Verified.
  - Test-coverage references (`tests/calc.test.js:20-23`, `:25-28`,
    `tests/evaluate.test.js:14-16`) — ✅ Verified.
- **Reasoning:** Verification rate is 92% (≥ 90%) and **every critical claim — all
  three buggy locations, all three root-cause diagnoses, and all pinning tests —
  is Verified against the real source.** The two remaining issues are
  non-critical: one False auxiliary statistic (a miscounted passing-test tally,
  off by one) and one Partial variable-name imprecision in the SEC-001 data-flow
  description. Neither touches a bug location, diagnosis, or proposed fix
  direction, so the single-False-critical-claim cap (which would force L2) does
  not apply. Per the scoring rule this lands at **L4 (Good)** rather than L5,
  because the document is not 100% verified. Result is **PASS** (L4 ≥ L3): the
  Bug Planner may use this research with minor caution, correcting the passing-test
  count and the `argv`/`args` naming.

## References
Every source location I opened and checked (reproducible):
- src/calc.js:16-18 — `sum`
- src/calc.js:29-31 — `average` (defective line 30)
- src/calc.js:43-45 — `applyDiscount` (defective line 44)
- src/calc.js:47 — module exports / file length
- src/evaluate.js:22-24 — `evaluateExpression` (defective line 23)
- src/evaluate.js:26 — module exports / file length
- src/index.js:33 — `const [command, ...args] = argv;`
- src/index.js:39 — `avg` dispatch
- src/index.js:40-43 — `discount` dispatch block
- src/index.js:44-45 — `calc` dispatch / `evaluateExpression` call
- src/index.js:52 — `const argv = process.argv.slice(2);`
- tests/calc.test.js:12-14 — `sum` passing test
- tests/calc.test.js:16-18 — `average` non-empty passing test
- tests/calc.test.js:20-23 — BUG-001 failing test
- tests/calc.test.js:25-28 — BUG-002 failing test
- tests/evaluate.test.js:8-12 — anticipatory comment
- tests/evaluate.test.js:14-16 — benign passing test
