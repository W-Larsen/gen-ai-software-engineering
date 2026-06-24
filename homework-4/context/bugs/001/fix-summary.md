# Fix Summary

## Changes Made

---

### Change 1 — BUG-001

- **File:** `src/calc.js`
- **Location:** function `average(numbers)`, lines 29–31 (declared line 29)
- **Before:**
  ```javascript
  function average(numbers) {
    return sum(numbers) / numbers.length;
  }
  ```
- **After:**
  ```javascript
  function average(numbers) {
    if (numbers.length === 0) return 0;
    return sum(numbers) / numbers.length;
  }
  ```
- **Test Result:** PASS
  ```
  ✔ sum adds a list of numbers (0.636ms)
  ✔ average of a non-empty list (0.066ms)
  ✔ average of an empty list is 0 (BUG-001) (0.043ms)
  ✖ applyDiscount applies a percentage (BUG-002)   ← expected; not yet fixed
  ✔ evaluateExpression computes a simple arithmetic expression (0.559ms)
  pass 4 / fail 1
  ```
  The BUG-001 pinning test (`average of an empty list is 0`) flipped from failing to passing. The remaining failure is BUG-002, which is by design at this stage.

---

### Change 2 — BUG-002

- **File:** `src/calc.js`
- **Location:** function `applyDiscount(price, percent)`, lines 43–45 (declared line 43)
- **Before:**
  ```javascript
  function applyDiscount(price, percent) {
    return price - percent;
  }
  ```
- **After:**
  ```javascript
  function applyDiscount(price, percent) {
    return price - (price * percent) / 100;
  }
  ```
- **Test Result:** PASS
  ```
  ✔ sum adds a list of numbers (0.635ms)
  ✔ average of a non-empty list (0.066ms)
  ✔ average of an empty list is 0 (BUG-001) (0.043ms)
  ✔ applyDiscount applies a percentage (BUG-002) (0.041ms)
  ✔ evaluateExpression computes a simple arithmetic expression (0.559ms)
  pass 5 / fail 0
  ```
  All 5 tests green after this change.

---

### Change 3 — SEC-001

- **File:** `src/evaluate.js`
- **Location:** function `evaluateExpression(expr)`, lines 22–24 (declared line 22)
- **Before:**
  ```javascript
  function evaluateExpression(expr) {
    return eval(expr); // eslint-disable-line no-eval
  }
  ```
- **After:**
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
- **Test Result:** PASS
  ```
  ✔ sum adds a list of numbers (0.672ms)
  ✔ average of a non-empty list (0.061ms)
  ✔ average of an empty list is 0 (BUG-001) (0.044ms)
  ✔ applyDiscount applies a percentage (BUG-002) (0.042ms)
  ✔ evaluateExpression computes a simple arithmetic expression (0.668ms)
  pass 5 / fail 0
  duration_ms 83.80
  ```
  The existing benign test (`evaluateExpression('2 + 3') === 5`) continues to pass. The `eval()` call and its `// eslint-disable-line no-eval` annotation have been removed; CWE-95 is eliminated.

---

## Overall Status

**COMPLETE**

All three issues (BUG-001, BUG-002, SEC-001) were applied in the order specified by the plan. After each change `npm test` was executed. The test suite progressed from 2 failing / 3 passing → 1 failing / 4 passing → 0 failing / 5 passing, ending in a clean run. No test files were modified.

---

## Manual Verification

1. **BUG-001 — `average([])`**
   - Run `node -e "const { average } = require('./src/calc'); console.log(average([])); console.log(average([2,4,6]));"` from the project root.
   - Expected output: `0` (first line) and `4` (second line).

2. **BUG-002 — `applyDiscount`**
   - Run `node -e "const { applyDiscount } = require('./src/calc'); console.log(applyDiscount(200, 10)); console.log(applyDiscount(100, 25));"`.
   - Expected output: `180` and `75`.

3. **SEC-001 — injection prevention**
   - Benign input still works: `node -e "const { evaluateExpression } = require('./src/evaluate'); console.log(evaluateExpression('2 + 3'));"` → `5`.
   - Malicious input is now rejected — the following should throw, not execute:
     - `node -e "const { evaluateExpression } = require('./src/evaluate'); evaluateExpression(\"process.exit(1)\");"` → throws `Error: Invalid expression: only numbers and + - * / ( ) are allowed`.
     - `node -e "const { evaluateExpression } = require('./src/evaluate'); evaluateExpression(\"require('child_process').execSync('id')\");"` → throws the same error.
   - Division by zero is guarded: `evaluateExpression('1 / 0')` → throws `Error: Invalid expression: division by zero`.
   - Operator precedence is preserved: `evaluateExpression('2 + 3 * 4')` → `14`; `evaluateExpression('(2 + 3) * 4')` → `20`.
   - If the ledger CLI is built/linked, exercise the `calc` command end-to-end: `ledger calc "10 * (3 + 2)"` → `50`, and `ledger calc "process.exit(1)"` → error with non-zero exit code (not a silent process kill).

---

## References

- **Implementation plan:** `context/bugs/001/implementation-plan.md`
- **Source research:** `context/bugs/001/research/verified-research.md`, `context/bugs/001/research/codebase-research.md`
- **Files modified:**
  - `src/calc.js` — BUG-001 (`average` guard) and BUG-002 (`applyDiscount` formula)
  - `src/evaluate.js` — SEC-001 (replaced `eval()` with recursive-descent parser)
- **Tests:** `tests/calc.test.js`, `tests/evaluate.test.js` (read-only; not modified)
- **Related IDs:** BUG-001, BUG-002, SEC-001 (CWE-95)
