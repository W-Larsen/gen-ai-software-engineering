#!/usr/bin/env node
'use strict';

const { sum, average, applyDiscount } = require('./calc');
const { evaluateExpression } = require('./evaluate');

const USAGE = `ledger - tiny CLI for quick math on amounts

Usage:
  ledger sum <a> <b> ...        Sum the given numbers
  ledger avg <a> <b> ...        Average of the given numbers
  ledger discount <price> <pct> Apply a percentage discount to a price
  ledger calc "<expr>"          Evaluate an arithmetic expression

Examples:
  ledger sum 1 2 3
  ledger avg 2 4 6
  ledger discount 200 10
  ledger calc "2 + 3 * 4"
`;

function toNumbers(args) {
  return args.map((a) => {
    const n = Number(a);
    if (Number.isNaN(n)) {
      throw new Error(`not a number: ${a}`);
    }
    return n;
  });
}

function run(argv) {
  const [command, ...args] = argv;

  switch (command) {
    case 'sum':
      return sum(toNumbers(args));
    case 'avg':
      return average(toNumbers(args));
    case 'discount': {
      const [price, percent] = toNumbers(args);
      return applyDiscount(price, percent);
    }
    case 'calc':
      return evaluateExpression(args.join(' '));
    default:
      return null;
  }
}

function main() {
  const argv = process.argv.slice(2);

  if (argv.length === 0 || argv[0] === 'help' || argv[0] === '--help') {
    process.stdout.write(USAGE);
    return;
  }

  try {
    const result = run(argv);
    if (result === null) {
      process.stderr.write(`unknown command: ${argv[0]}\n\n${USAGE}`);
      process.exitCode = 1;
      return;
    }
    process.stdout.write(`${result}\n`);
  } catch (err) {
    process.stderr.write(`error: ${err.message}\n`);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}

module.exports = { run };
