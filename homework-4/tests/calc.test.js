'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

const { sum, average, applyDiscount } = require('../src/calc');

// These tests assert the CORRECT behavior. In the "before" state two of them
// fail, demonstrating the seeded bugs (BUG-001, BUG-002). After the pipeline's
// bug-fixer applies the fixes, the whole suite goes green.

test('sum adds a list of numbers', () => {
  assert.equal(sum([1, 2, 3]), 6);
});

test('average of a non-empty list', () => {
  assert.equal(average([2, 4, 6]), 4);
});

test('average of an empty list is 0 (BUG-001)', () => {
  // Buggy implementation returns NaN (division by zero).
  assert.equal(average([]), 0);
});

test('applyDiscount applies a percentage (BUG-002)', () => {
  // Buggy implementation returns 190 (subtracts percent as a flat amount).
  assert.equal(applyDiscount(200, 10), 180);
});
