'use strict';

/**
 * Pure math helpers for the ledger CLI.
 *
 * NOTE: This file ships in the "before" (buggy) state for the 4-agent pipeline.
 * Two bugs are intentionally seeded here — see context/bugs/001/bug-context.md
 * (BUG-001 and BUG-002).
 */

/**
 * Sum a list of numbers.
 * @param {number[]} numbers
 * @returns {number}
 */
function sum(numbers) {
  return numbers.reduce((total, n) => total + n, 0);
}

/**
 * Average of a list of numbers.
 *
 * BUG-001: divides by numbers.length with no empty-array guard, so average([])
 * returns NaN (division by zero) instead of a sensible value.
 *
 * @param {number[]} numbers
 * @returns {number}
 */
function average(numbers) {
  if (numbers.length === 0) return 0;
  return sum(numbers) / numbers.length;
}

/**
 * Apply a percentage discount to a price.
 *
 * BUG-002: subtracts the percent as a flat amount instead of computing a
 * percentage. applyDiscount(200, 10) returns 190 but should return 180.
 *
 * @param {number} price
 * @param {number} percent
 * @returns {number}
 */
function applyDiscount(price, percent) {
  return price - (price * percent) / 100;
}

module.exports = { sum, average, applyDiscount };
