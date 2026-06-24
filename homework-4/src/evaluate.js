'use strict';

/**
 * Expression evaluation for the `calc` command.
 *
 * NOTE: This file ships in the "before" (insecure) state for the 4-agent
 * pipeline. One security issue is intentionally seeded here — see
 * context/bugs/001/bug-context.md (SEC-001).
 */

/**
 * Evaluate an arithmetic expression string supplied on the command line.
 *
 * SEC-001 (code injection / arbitrary code execution): the untrusted CLI input
 * is passed straight to eval(), so `ledger calc "process.exit(1)"` or
 * `ledger calc "require('child_process').execSync('id')"` would execute.
 * Intended fix: replace eval() with a restricted numeric-expression parser.
 *
 * @param {string} expr
 * @returns {number}
 */
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

module.exports = { evaluateExpression };
