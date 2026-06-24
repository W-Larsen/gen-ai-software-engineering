# Codebase Research — Bug 001 (ledger CLI)

**Researcher:** Bug Researcher
**Date:** 2026-06-24
**Scope:** `src/` and `tests/` of the ledger CLI mini-application.
**Method:** Each issue below was verified by reading the current source file directly.
Every `file:line` reference and code snippet was copied verbatim from the file as
it exists now. No source code was modified during this research.

---

## Summary

| ID | File | Line(s) | Class | Severity | Test coverage |
|----|------|---------|-------|----------|---------------|
| BUG-001 | `src/calc.js` | 30 | Logic / missing empty-array guard (division by zero) | Medium | `tests/calc.test.js:20-23` (failing) |
| BUG-002 | `src/calc.js` | 44 | Logic / wrong formula | High | `tests/calc.test.js:25-28` (failing) |
| SEC-001 | `src/evaluate.js` | 23 | Injection / arbitrary code execution (CWE-95) | Critical | Static finding — no failing test (`tests/evaluate.test.js:14-16` only checks benign input) |

Expected `npm test` result in the current "before" state: **2 failing, 2 passing**.

---

## BUG-001 — `average([])` returns `NaN`

- **File:** `src/calc.js`
- **Function:** `average(numbers)` (declared at `src/calc.js:29`)
- **Defective line:** `src/calc.js:30`
- **Class:** Logic / missing guard — division by zero.
- **Severity:** Medium

### Verbatim code (`src/calc.js:29-31`)

```javascript
function average(numbers) {
  return sum(numbers) / numbers.length;
}
```

### Root cause

When `numbers` is the empty array `[]`, `sum(numbers)` returns `0`
(see `sum` at `src/calc.js:16-18`) and `numbers.length` is `0`. The expression
`0 / 0` evaluates to `NaN`. There is no guard for the empty-array case, so the
function propagates `NaN` to its callers (including the `avg` command in
`src/index.js:39`).

### Failing test that pins the expected behavior (`tests/calc.test.js:20-23`)

```javascript
test('average of an empty list is 0 (BUG-001)', () => {
  // Buggy implementation returns NaN (division by zero).
  assert.equal(average([]), 0);
});
```

### Proposed fix direction

Add an empty-array guard before dividing: if `numbers.length === 0`, return `0`
(the value the test expects). Otherwise compute `sum(numbers) / numbers.length`
as today. Example direction (do not apply here — research only):

```javascript
function average(numbers) {
  if (numbers.length === 0) return 0;
  return sum(numbers) / numbers.length;
}
```

---

## BUG-002 — `applyDiscount` subtracts percent as a flat amount

- **File:** `src/calc.js`
- **Function:** `applyDiscount(price, percent)` (declared at `src/calc.js:43`)
- **Defective line:** `src/calc.js:44`
- **Class:** Logic / wrong formula (incorrect monetary calculation).
- **Severity:** High

### Verbatim code (`src/calc.js:43-45`)

```javascript
function applyDiscount(price, percent) {
  return price - percent;
}
```

### Root cause

The function is meant to apply `percent` as a **percentage** of `price`, but it
subtracts `percent` as a flat amount. For `applyDiscount(200, 10)` it returns
`200 - 10 = 190`, whereas the correct percentage discount is
`200 - (200 * 10) / 100 = 180`. The `percent` value is never scaled relative to
`price`. This feeds the `discount` command at `src/index.js:40-43`.

### Failing test that pins the expected behavior (`tests/calc.test.js:25-28`)

```javascript
test('applyDiscount applies a percentage (BUG-002)', () => {
  // Buggy implementation returns 190 (subtracts percent as a flat amount).
  assert.equal(applyDiscount(200, 10), 180);
});
```

### Proposed fix direction

Compute the discount as a fraction of `price`:
`price - (price * percent) / 100`. Example direction (do not apply here —
research only):

```javascript
function applyDiscount(price, percent) {
  return price - (price * percent) / 100;
}
```

---

## SEC-001 — Arbitrary code execution via `eval()`

- **File:** `src/evaluate.js`
- **Function:** `evaluateExpression(expr)` (declared at `src/evaluate.js:22`)
- **Defective line:** `src/evaluate.js:23`
- **Class:** Injection / arbitrary code execution — CWE-95 (Improper Neutralization
  of Directives in Dynamically Evaluated Code, "Eval Injection").
- **Severity:** Critical

### Verbatim code (`src/evaluate.js:22-24`)

```javascript
function evaluateExpression(expr) {
  return eval(expr); // eslint-disable-line no-eval
}
```

### Untrusted data flow

The CLI passes user-controlled input straight into this function with no
validation or sanitization:

- `src/index.js:45` — the `calc` command:

```javascript
    case 'calc':
      return evaluateExpression(args.join(' '));
```

- `src/index.js:52` builds `args` from `process.argv.slice(2)`, so the raw
  command-line string reaches `eval()` unchanged.

### Root cause

`eval(expr)` executes its string argument as full JavaScript in the process
context. Because `expr` is attacker-controlled CLI input, any JavaScript runs
with the privileges of the Node process. Examples (do **not** run with hostile
input):

- `ledger calc "process.exit(1)"` — terminates the process.
- `ledger calc "require('child_process').execSync('id').toString()"` — executes
  an arbitrary shell command.

The benign path `ledger calc "2 + 3"` returns `5`, which is why
`tests/evaluate.test.js:14-16` passes and the issue does not surface as a failing
test — it is a static-review finding only.

### Existing (benign-only) test (`tests/evaluate.test.js:14-16`)

```javascript
test('evaluateExpression computes a simple arithmetic expression', () => {
  assert.equal(evaluateExpression('2 + 3'), 5);
});
```

### Proposed fix direction

Replace `eval()` with a restricted numeric-expression parser/evaluator that only
permits numbers, whitespace, and the operators `+ - * / ( )`. Approach:

1. Validate input against a strict allowlist (e.g. reject any character outside
   `[0-9.\s+\-*/()]`) and throw on disallowed input.
2. Evaluate the sanitized arithmetic with a safe parser (a small
   tokenizer/shunting-yard evaluator, or a vetted math library) rather than the
   JavaScript engine.
3. Add a regression test that asserts non-numeric/malicious input is rejected
   (the existing comment at `tests/evaluate.test.js:8-12` anticipates a "rejects
   non-numeric input" test after the fix).

This preserves the benign `evaluateExpression('2 + 3') === 5` behavior while
removing the arbitrary-code-execution capability.

---

## Verification notes

- `src/calc.js` read in full (47 lines + trailing newline); `average` body is line
  30, `applyDiscount` body is line 44 — confirmed.
- `src/evaluate.js` read in full (26 lines + trailing newline); `eval(expr)` is
  line 23 — confirmed.
- `src/index.js` read in full; `calc` dispatch is line 45, `argv` slice is line 52,
  `avg` dispatch line 39, `discount` block lines 40-43 — confirmed.
- `tests/calc.test.js` BUG-001 test lines 20-23, BUG-002 test lines 25-28 —
  confirmed.
- `tests/evaluate.test.js` benign test lines 14-16 — confirmed.
- No source files were modified.
