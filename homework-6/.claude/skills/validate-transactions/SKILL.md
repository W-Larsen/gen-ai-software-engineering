---
name: validate-transactions
description: Validate all transactions in sample-transactions.json via the validator's --dry-run mode, without running the full pipeline
---

# Validate transactions (dry run)

Validate every transaction in `sample-transactions.json` **without** running the full pipeline.
This skill **only invokes the existing validator script** — do not re-implement validation logic.

Optional extra args (passed through to the validator): `$ARGUMENTS`

## Steps

1. **Run the validator in dry-run mode:** execute
   `python agents/transaction_validator.py --dry-run $ARGUMENTS` from the `homework-6/` directory.
   Dry-run reads `sample-transactions.json`, validates each row, and writes **nothing** to
   `shared/`.
2. **Report counts:** total count, valid count, invalid count, and the rejection reason for each
   invalid transaction (as printed by the script).
3. **Show a table:** present the results as a table — one row per transaction with its id, status
   (valid / invalid), and reason.

Report the counts and table; do not run the fraud detector, compliance checker, or integrator.
