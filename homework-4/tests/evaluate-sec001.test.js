'use strict';

/**
 * Focused tests for the security fix applied to src/evaluate.js (SEC-001).
 *
 * SEC-001: evaluateExpression() — replaced eval() with a safe recursive-descent
 * parser that rejects any input not matching the allowlist:
 *   digits, decimal points, whitespace, and operators + - * / ( )
 *
 * Previously, arbitrary code such as `process.exit(1)` or
 * `require('child_process').execSync('id')` could be executed. After the fix
 * such input throws an Error before any parsing occurs.
 *
 * FIRST compliance:
 *   F — pure in-memory parsing; no I/O, no network, no sleep; each test < 5 ms
 *   I — each test is fully self-contained; no shared mutable state
 *   R — deterministic; inputs are literals; no Date/Math.random/env dependency
 *   S — explicit assert.equal / assert.throws with concrete expected values
 *   T — covers only the changed function from fix-summary.md SEC-001
 */

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { evaluateExpression } = require('../src/evaluate');

// ─── SEC-001 regression: injection strings must be rejected ──────────────────

test('evaluateExpression: regression SEC-001 — rejects process.exit() injection', () => {
  // Before the fix: eval('process.exit(1)') would kill the process.
  // After the fix:  allowlist check rejects non-numeric characters immediately.
  assert.throws(
    () => evaluateExpression('process.exit(1)'),
    { message: 'Invalid expression: only numbers and + - * / ( ) are allowed' }
  );
});

test('evaluateExpression: regression SEC-001 — rejects require() / child_process injection', () => {
  // Before the fix: eval("require('child_process').execSync('id')") ran shell commands.
  // After the fix:  allowlist rejects letters and single-quotes immediately.
  assert.throws(
    () => evaluateExpression("require('child_process').execSync('id')"),
    { message: 'Invalid expression: only numbers and + - * / ( ) are allowed' }
  );
});

// ─── Happy path: basic arithmetic operations ──────────────────────────────────

test('evaluateExpression: subtraction — 10 - 4 = 6', () => {
  assert.equal(evaluateExpression('10 - 4'), 6);
});

test('evaluateExpression: multiplication — 3 * 4 = 12', () => {
  assert.equal(evaluateExpression('3 * 4'), 12);
});

test('evaluateExpression: division — 10 / 2 = 5', () => {
  assert.equal(evaluateExpression('10 / 2'), 5);
});

test('evaluateExpression: decimal numbers — 1.5 + 2.5 = 4', () => {
  assert.equal(evaluateExpression('1.5 + 2.5'), 4);
});

// ─── Happy path: operator precedence and parentheses ─────────────────────────

test('evaluateExpression: operator precedence — multiplication before addition (2 + 3 * 4 = 14)', () => {
  // Verifies the parser applies standard precedence (PEMDAS), not left-to-right.
  assert.equal(evaluateExpression('2 + 3 * 4'), 14);
});

test('evaluateExpression: parentheses override precedence ((2 + 3) * 4 = 20)', () => {
  assert.equal(evaluateExpression('(2 + 3) * 4'), 20);
});

test('evaluateExpression: parentheses with multiple operators — 10 * (3 + 2) = 50', () => {
  assert.equal(evaluateExpression('10 * (3 + 2)'), 50);
});

test('evaluateExpression: nested parentheses — (2 + (3 * 4)) = 14', () => {
  assert.equal(evaluateExpression('(2 + (3 * 4))'), 14);
});

// ─── Edge cases: error handling ───────────────────────────────────────────────

test('evaluateExpression: throws TypeError for non-string input (number)', () => {
  assert.throws(
    () => evaluateExpression(42),
    { name: 'TypeError', message: 'Expression must be a string' }
  );
});

test('evaluateExpression: throws TypeError for non-string input (null)', () => {
  assert.throws(
    () => evaluateExpression(null),
    { name: 'TypeError', message: 'Expression must be a string' }
  );
});

test('evaluateExpression: throws on whitespace-only input (no tokens found)', () => {
  // Whitespace passes the allowlist check but yields no tokens.
  assert.throws(
    () => evaluateExpression('   '),
    { message: 'Invalid expression: no tokens found' }
  );
});

test('evaluateExpression: throws on division by zero', () => {
  assert.throws(
    () => evaluateExpression('1 / 0'),
    { message: 'Invalid expression: division by zero' }
  );
});

test('evaluateExpression: throws on unbalanced opening parenthesis', () => {
  assert.throws(
    () => evaluateExpression('(2 + 3'),
    { message: 'Invalid expression: missing closing parenthesis' }
  );
});
