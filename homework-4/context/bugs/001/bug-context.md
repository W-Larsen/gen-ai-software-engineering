# Bug Context — 001 (ledger CLI)

This is the seeded "before" state of the sample mini-application (`src/`) that the
4-agent pipeline operates on. It contains **two functional bugs** and **one security
issue**, documented below so the Bug Researcher / Verifier / Planner / Fixer have a
starting brief and the Security Verifier and Unit Test Generator have concrete targets.

Reproduce the failing tests at any time with:

```bash
npm test
```

Expected before-fix result: **2 failing, 2 passing** (the two functional bugs). The
security issue is found by static review, not by a failing test.

---

## BUG-001 — `average([])` returns `NaN`

- **File:** `src/calc.js` — `average(numbers)`
- **Class:** logic / missing guard (division by zero)
- **Symptom:** `average([])` returns `NaN` instead of a sensible value.
- **Expected:** `average([]) === 0`
- **Actual:** `NaN` — `sum(numbers) / numbers.length` divides by `0` when the list is empty.
- **Severity:** Medium
- **Repro:** `node -e "console.log(require('./src/calc').average([]))"` → `NaN`
  (also covered by the test "average of an empty list is 0 (BUG-001)").

## BUG-002 — `applyDiscount` subtracts percent as a flat amount

- **File:** `src/calc.js` — `applyDiscount(price, percent)`
- **Class:** logic / wrong formula
- **Symptom:** the discount is applied as a flat subtraction, not a percentage.
- **Expected:** `applyDiscount(200, 10) === 180` (i.e. `price - (price * percent) / 100`)
- **Actual:** `190` — the implementation returns `price - percent`.
- **Severity:** High (incorrect monetary calculation)
- **Repro:** `npm start discount 200 10` → prints `190`
  (also covered by the test "applyDiscount applies a percentage (BUG-002)").

## SEC-001 — Arbitrary code execution via `eval()`

- **File:** `src/evaluate.js` — `evaluateExpression(expr)`
- **Class:** Injection / arbitrary code execution (CWE-95)
- **Symptom:** untrusted CLI input is passed directly to `eval()`.
- **Impact:** `ledger calc "<expr>"` can execute any JavaScript, e.g.
  `ledger calc "process.exit(1)"` or
  `ledger calc "require('child_process').execSync('id').toString()"`.
- **Severity:** Critical
- **Intended fix:** replace `eval()` with a restricted numeric-expression parser that only
  permits numbers and the operators `+ - * / ( )`.
- **Repro (do NOT run with hostile input on a real machine):**
  `npm start calc "2 + 3"` → `5` (benign), but the same path executes arbitrary code.

---

## Pipeline artifacts (populated as the pipeline runs)

The 4-agent pipeline will produce these files; they reference the bugs above:

- `research/codebase-research.md` — Bug Researcher output
- `research/verified-research.md` — Research Verifier output (quality per the
  `research-quality-measurement` skill)
- `implementation-plan.md` — Bug Planner output
- `fix-summary.md` — Bug Fixer output (changes applied + test results)
- `security-report.md` — Security Verifier output (expects to flag SEC-001)
- `test-report.md` — Unit Test Generator output (FIRST-compliant tests for the fixes)
