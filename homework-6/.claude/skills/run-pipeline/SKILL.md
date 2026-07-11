---
name: run-pipeline
description: Run the multi-agent banking pipeline end-to-end (integrator.py) and summarize results from shared/results/
---

# Run the banking pipeline end-to-end

Run the multi-agent banking pipeline and report what happened. This skill **only orchestrates the
existing scripts** — do not re-implement or reason about pipeline logic yourself.

Optional extra args (passed through to `integrator.py`, e.g. `--sample <file>`): `$ARGUMENTS`

## Steps

1. **Check input exists:** confirm `sample-transactions.json` is present (fail early with a clear
   message if not).
2. **Clear shared state:** remove the contents of `shared/input/`, `shared/processing/`,
   `shared/output/`, and `shared/results/` so the run starts clean (recreate the empty dirs; keep
   any `.gitkeep`).
3. **Run the pipeline:** execute `python integrator.py $ARGUMENTS` from the `homework-6/` directory.
4. **Show the summary:** print the contents of `shared/results/summary.json` (total, validated,
   cleared, flagged, rejected, requires_report, malformed_input_count).
5. **Report rejections:** list every transaction in `shared/results/` whose `data.status` is
   `rejected` (or `decision` is `rejected`) together with its `reason`, and confirm that every id
   from `sample-transactions.json` produced a terminal result.

Report the summary and any rejected transactions concisely; do not modify agent code.
