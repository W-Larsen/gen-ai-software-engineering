# Implementation Plan — Bug 001 (ledger CLI)

**Author:** Bug Planner
**Date:** 2026-06-24
**Source research:**
- `context/bugs/001/research/verified-research.md` (Verification: PASS, L4 🟢 Good — 23/25 claims verified)
- `context/bugs/001/research/codebase-research.md`

**Scope:** Fix three issues — BUG-001, BUG-002, SEC-001 — in `src/`. No tests are modified by this plan (the `unit-test-generator` adds the SEC-001 regression test afterward).

**Test command (for every issue):** `npm test`

> Notes carried from verification (apply with caution):
> - The "before" state is actually **2 failing / 3 passing**, not "2 failing / 2 passing" (the research summary miscounted by one). The two *failing* tests are the BUG-001 and BUG-002 pinning tests.
> - SEC-001 has no failing test in the "before" state; it is a static finding. The benign test `evaluateExpression('2 + 3') === 5` must keep passing after the fix.

---

## BUG-001 — `average([])` returns `NaN`

- **File path:** `src/calc.js`
- **Exact location:** function `average(numbers)`, body at line 30 (declared line 29).
- **Class / Severity:** Logic / missing empty-array guard (division by zero) — Medium.
- **Pinning test:** `tests/calc.test.js:20-23` (currently failing).

### BEFORE (exact)

```javascript
function average(numbers) {
  return sum(numbers) / numbers.length;
}
```

### AFTER (exact)

```javascript
function average(numbers) {
  if (numbers.length === 0) return 0;
  return sum(numbers) / numbers.length;
}
```

### Rationale
When `numbers` is `[]`, `sum(numbers)` is `0` and `numbers.length` is `0`, so `0 / 0 === NaN`. The guard returns `0` (the value the pinning test expects) for the empty case and leaves all non-empty behavior unchanged.

### Verify
```
npm test
```
Expect the `average of an empty list is 0 (BUG-001)` test to pass; `sum` and `average of a non-empty list` tests stay green.

---

## BUG-002 — `applyDiscount` subtracts percent as a flat amount

- **File path:** `src/calc.js`
- **Exact location:** function `applyDiscount(price, percent)`, body at line 44 (declared line 43).
- **Class / Severity:** Logic / wrong formula (incorrect monetary calculation) — High.
- **Pinning test:** `tests/calc.test.js:25-28` (currently failing).

### BEFORE (exact)

```javascript
function applyDiscount(price, percent) {
  return price - percent;
}
```

### AFTER (exact)

```javascript
function applyDiscount(price, percent) {
  return price - (price * percent) / 100;
}
```

### Rationale
`percent` must be applied as a percentage of `price`, not a flat subtraction. For `applyDiscount(200, 10)`: `200 - (200 * 10) / 100 = 200 - 20 = 180`, matching the pinning test (the buggy version returned `190`).

### Verify
```
npm test
```
Expect the `applyDiscount applies a percentage (BUG-002)` test to pass.

---

## SEC-001 — Arbitrary code execution via `eval()`

- **File path:** `src/evaluate.js`
- **Exact location:** function `evaluateExpression(expr)`, body at line 23 (declared line 22).
- **Class / Severity:** Injection / arbitrary code execution — CWE-95 — Critical.
- **Untrusted data flow:** `src/index.js:45` (`calc` command) calls `evaluateExpression(args.join(' '))`; `args` derives from `process.argv.slice(2)` (`src/index.js:52`, destructured at `src/index.js:33`). Raw CLI input reaches `eval()` unchanged.
- **Existing test (must keep passing):** `tests/evaluate.test.js:14-16` — `evaluateExpression('2 + 3') === 5`.

### Required change
Replace `eval()` with a **safe arithmetic parser** that only allows numbers and the operators `+ - * / ( )` (plus whitespace and decimal points). The parser must reject any other characters/input by throwing.

### BEFORE (exact)

```javascript
function evaluateExpression(expr) {
  return eval(expr); // eslint-disable-line no-eval
}
```

### AFTER (exact)

```javascript
function evaluateExpression(expr) {
  if (typeof expr !== 'string') {
    throw new TypeError('Expression must be a string');
  }

  // Allowlist: digits, decimal points, whitespace, and the operators + - * / ( )
  if (!/^[0-9.\s+\-*/()]+$/.test(expr)) {
    throw new Error('Invalid expression: only numbers and + - * / ( ) are allowed');
  }

  // Tokenize into numbers, operators, and parentheses.
  const tokens = expr.match(/\d+(?:\.\d+)?|[+\-*/()]/g);
  if (!tokens) {
    throw new Error('Invalid expression: no tokens found');
  }

  let pos = 0;
  const peek = () => tokens[pos];
  const next = () => tokens[pos++];

  // Recursive-descent parser (grammar):
  //   expression := term (('+' | '-') term)*
  //   term       := factor (('*' | '/') factor)*
  //   factor     := number | '(' expression ')'
  function parseExpression() {
    let value = parseTerm();
    while (peek() === '+' || peek() === '-') {
      const op = next();
      const rhs = parseTerm();
      value = op === '+' ? value + rhs : value - rhs;
    }
    return value;
  }

  function parseTerm() {
    let value = parseFactor();
    while (peek() === '*' || peek() === '/') {
      const op = next();
      const rhs = parseFactor();
      if (op === '/' && rhs === 0) {
        throw new Error('Invalid expression: division by zero');
      }
      value = op === '*' ? value * rhs : value / rhs;
    }
    return value;
  }

  function parseFactor() {
    const token = next();
    if (token === '(') {
      const value = parseExpression();
      if (next() !== ')') {
        throw new Error('Invalid expression: missing closing parenthesis');
      }
      return value;
    }
    const num = Number(token);
    if (Number.isNaN(num)) {
      throw new Error(`Invalid expression: unexpected token "${token}"`);
    }
    return num;
  }

  const result = parseExpression();
  if (pos !== tokens.length) {
    throw new Error('Invalid expression: unexpected trailing input');
  }
  return result;
}
```

### Rationale
- `eval()` executes any JavaScript with the Node process's privileges; attacker-controlled CLI input (e.g. `ledger calc "require('child_process').execSync('id')"`) would run. Removing `eval` eliminates CWE-95.
- The character allowlist (`/^[0-9.\s+\-*/()]+$/`) rejects identifiers, function calls, and any non-arithmetic input *before* parsing — only numbers, whitespace, decimal points, and `+ - * / ( )` survive.
- The recursive-descent evaluator computes the result without invoking the JavaScript engine, preserving correct operator precedence and parentheses.
- Benign input is unchanged: `evaluateExpression('2 + 3')` still returns `5`, so `tests/evaluate.test.js:14-16` keeps passing.
- The `// eslint-disable-line no-eval` comment is removed along with `eval`.

### Verify
```
npm test
```
Expect `evaluateExpression computes a simple arithmetic expression` to keep passing. After this fix, the `unit-test-generator` is expected to add a "rejects non-numeric input" regression test (anticipated by the comment at `tests/evaluate.test.js:8-12`); malicious input like `process.exit(1)` should now throw rather than execute.

---

## Execution order & overall verification

1. Apply BUG-001 (`src/calc.js:29-31`).
2. Apply BUG-002 (`src/calc.js:43-45`).
3. Apply SEC-001 (`src/evaluate.js:22-24`).
4. Run `npm test` after each change and once at the end.

**Expected final state:** all 5 existing tests pass (`2 failing → 0 failing`). No test files are modified by this plan.
