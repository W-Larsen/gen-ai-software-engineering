'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { evaluateExpression } = require('../src/evaluate');

// SEC-001 (the eval-based injection) is a *static* finding for the
// security-verifier, not a failing test. We deliberately do NOT feed malicious
// input here — that would execute arbitrary code and could kill the test
// runner. After the fix, the unit-test-generator is expected to add a
// "rejects non-numeric input" regression test.

test('evaluateExpression computes a simple arithmetic expression', () => {
  assert.equal(evaluateExpression('2 + 3'), 5);
});
