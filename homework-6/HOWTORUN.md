# How To Run — Banking Transaction-Processing Pipeline

Copy-pasteable steps from a clean checkout to a full demo. All commands are run from the
`homework-6/` directory unless noted otherwise. Commands are shown for `bash`/PowerShell (the
`python` invocation is identical on both).

## 0. Quick start — `./demo.sh`

If you just want to see everything work, run the demo script. It needs nothing installed beyond
Python 3.11+ and `curl`, and performs every step in this document with no manual intervention:

```bash
bash demo.sh
```

It creates a local `.venv` (first run only), installs the dependencies, wipes `shared/` and
`logs/audit.log` for a clean slate, runs the validator dry-run, runs the full pipeline, runs the
test suite against the 80% coverage gate, calls the custom MCP tools in-process, then starts the
dashboard, submits the 8 sample transactions plus 2 randomly generated ones, and prints a live table
of each transaction as it moves through validator → fraud detector → compliance checker. When it
finishes it leaves the dashboard running so you can open it in a browser; Ctrl-C stops the server.

Useful flags:

| Flag | Effect |
| --- | --- |
| `--exit` | Tear the server down and exit when the demo finishes (CI-friendly). |
| `--slow` | Use the real 1–5s per-stage delays instead of the brisk demo delays. |
| `--no-tests` | Skip the pytest + coverage step. |
| `--skip-install` | Assume `.venv` already has the dependencies. |
| `--port N` | Start the dashboard on port `N` (default 8000; walks upward if taken). |

Sections 1–6 below are the manual equivalents of what `demo.sh` automates — read them to understand
each step, or run them individually.

## 1. Prerequisites

- **Python 3.11+** (this repository was developed and tested on Python 3.14.0rc2; the spec's
  minimum is 3.11). Check your version:

  ```bash
  python --version
  ```

- **Node.js + `npx`** (only needed if you want the `context7` MCP server from `.mcp.json` to run —
  it is launched via `npx -y @upstash/context7-mcp@latest`).

- Install the Python dependencies used by the pipeline, tests, frontend, and MCP server. The
  repository does not ship a `requirements.txt`/`pyproject.toml`, so install the packages directly
  (versions confirmed against this environment):

  ```bash
  python -m pip install "fastapi>=0.139" "uvicorn>=0.49" "pytest>=9.1" "pytest-cov>=7.1" "mcp>=1.28"
  ```

  **What to expect:** `pip` reports each package installed (or already satisfied). No other
  third-party runtime dependency is imported by `agents/`, `integrator.py`, `frontend/`, or
  `mcp/server.py`.

## 2. Run the pipeline end-to-end

```bash
python integrator.py
```

This creates `shared/{input,processing,output,results}/` and `logs/` if absent, loads all 8
records from `sample-transactions.json`, and drives each one through
Transaction Validator → Fraud Detector → Compliance Checker in order.

**What to expect:** stdout prints a `=== Banking Pipeline Summary ===` block — a JSON object with
`total`, `validated`, `rejected_at_validation`, `cleared`, `flagged`, `rejected_at_compliance`,
`requires_report`, `malformed_input_count`, and `error_count` — followed by the results path.

**How to know it worked:** `shared/results/` contains exactly 8 transaction result files
(`TXN001.json` … `TXN008.json`) plus `summary.json`, and `logs/audit.log` has new ISO 8601 entries
(one per agent operation). Optional custom sample file:

```bash
python integrator.py --sample path/to/other-transactions.json
```

Re-running `python integrator.py` a second time is idempotent — it will not create duplicate result
files or change any existing decision (each agent checks `shared/results/` first and returns the
stored outcome).

### 2a. Validate only (no full pipeline run)

To check the sample data without writing anything to `shared/`:

```bash
python agents/transaction_validator.py --dry-run
```

**What to expect:** `Total: 8`, `Valid: <n>`, `Invalid: <n>`, followed by a `Rejection reasons:`
list (e.g. `TXN006: invalid_currency_code:XYZ`) for any invalid rows. No files are written under
`shared/`.

## 3. Run the test suite with coverage

```bash
python -m pytest tests/ --cov=agents --cov=integrator --cov-report=term-missing
```

This is the exact command the coverage-gate hook (`.claude/hooks/coverage_gate.py`) runs before
allowing a `git push`; it fails (non-zero exit) if coverage over `agents` + `integrator` drops
below 80%.

**What to expect:** pytest collects and runs the suite in `tests/test_transaction_validator.py`,
`tests/test_fraud_detector.py`, `tests/test_compliance_checker.py`, `tests/test_integrator.py`
(the full-pipeline integration test), and `tests/test_mcp_server.py`, followed by a coverage table
per module and a `TOTAL` row.

**How to know it worked:** all tests pass and the `TOTAL` coverage percentage is at or above 80%
(the spec target is ≥ 90%). The integration test in `tests/test_integrator.py` runs `run_pipeline`
against an isolated `tmp_path` shared-root (via `PIPELINE_SHARED_ROOT`), so it never touches your
real `shared/` tree from step 2.

### 3a. Coverage gate in action (push-time enforcement)

The gate only fires on an actual `git push` (see `.claude/settings.json`,
`PreToolUse` hook on `Bash`, matcher on `git ... push`). It re-runs the same pytest/coverage
command; if coverage is below 80% it exits with status `2`, which Claude Code surfaces as a denied
tool call with the coverage output attached. No separate manual invocation is needed — it is wired
into the push path automatically when you push via Claude Code's `Bash` tool.

## 4. Launch the custom FastMCP server

Per `.mcp.json`, the `pipeline-status` MCP server is started as:

```bash
python mcp/server.py
```

**What to expect:** the process starts an MCP stdio server (`FastMCP("pipeline-status")`) and waits
for a client to connect over stdio — there is no standalone terminal output beyond process startup.
It is normally launched automatically by Claude Code (or any MCP-aware client) reading `.mcp.json`,
not run interactively by a human.

**How to know it worked:** from an MCP client (e.g. Claude Code with `.mcp.json` loaded), call:

- `get_transaction_status(transaction_id="TXN002")` → returns that transaction's current status
  (PII-safe fields only: `status`, `decision`, `reason`, `risk_score`, `requires_report`,
  `fraud_review`, `fraud_signals`, `currency`, `timestamp`) from `shared/results/`.
- `list_pipeline_results()` → returns `{total, by_decision, by_status, transactions, generated_at}`
  summarizing every processed transaction.
- Reading resource `pipeline://summary` → returns the latest `shared/results/summary.json` as text
  (or a computed fallback if `summary.json` does not yet exist).

Run `python integrator.py` (step 2) first so `shared/results/` is populated before querying.

The `context7` server in `.mcp.json` (`npx -y @upstash/context7-mcp@latest`) requires no separate
manual start either — an MCP client launches it on demand from the same `.mcp.json` config.

## 5. Launch the frontend dashboard

```bash
python -m uvicorn frontend.server:app --reload
```

(`uvicorn` may not be on `PATH` as a standalone command on every setup; the `python -m` form above
always works, per the note in `frontend/server.py`.)

**What to expect:** uvicorn prints `Uvicorn running on http://127.0.0.1:8000` (default host/port).
Open that URL in a browser to load `frontend/static/index.html` — a live dashboard with a
"Submit sample transactions" control.

**How to know it worked:**
- `GET /` serves the dashboard page.
- Clicking "Submit sample transactions" (or `POST /submit`) drops all 8 sample transactions into
  `shared/input/` and animates each one through the real validator → fraud detector → compliance
  checker functions with a simulated 1–5s pause per stage.
- `GET /api/status` returns a JSON array with one entry per `transaction_id`, each progressing
  through `received → processing → validated → scoring → scored → compliance → results`; the page
  polls this endpoint and updates each row live, without a full page reload.
- No response body (checked via browser dev tools or `curl http://127.0.0.1:8000/api/status`)
  contains an unmasked account number — accounts render as `ACC-***####`.
- `POST /clear` cancels any in-flight animation and wipes `shared/` + the live tracker so you can
  re-run the demo from a clean state.

## 6. Invoke the Claude Code skills

These are slash commands defined under `.claude/skills/` and are invoked from within a Claude Code
session (not the OS shell):

- **`/run-pipeline`** (`.claude/skills/run-pipeline/SKILL.md`) — checks `sample-transactions.json`
  exists, clears `shared/{input,processing,output,results}/`, runs `python integrator.py`, prints
  the `shared/results/summary.json` contents, and reports every rejected transaction with its
  reason.

  **What to expect / how to know it worked:** the assistant's reply shows the summary counts and
  lists any rejected `transaction_id`s (e.g. `TXN006: invalid_currency_code:XYZ`) — matching the
  output you already saw running step 2 manually.

- **`/validate-transactions`** (`.claude/skills/validate-transactions/SKILL.md`) — runs
  `python agents/transaction_validator.py --dry-run`, without touching `shared/` or invoking fraud
  detection/compliance, and reports total/valid/invalid counts plus a per-transaction table.

  **What to expect / how to know it worked:** the assistant's reply shows a table with each
  `transaction_id`, its valid/invalid status, and rejection reason where applicable — matching
  step 2a's output.

- **`/write-spec`** (`.claude/skills/write-spec/SKILL.md`) — regenerates `specification.md` from
  the bundled template; not part of the run-time demo, included here for completeness of the
  automation surface.

## Directory layout after a full run

```
shared/
├── input/       -- one JSON message per transaction (written by integrator/frontend)
├── processing/  -- transient: message being worked on by an agent
├── output/      -- validated/scored messages awaiting the next agent
└── results/     -- terminal outcome per transaction_id + summary.json
logs/
└── audit.log    -- append-only ISO 8601 audit trail, PII-masked
```

## Troubleshooting

- **`ImportError` for `fastapi`/`mcp` when running `frontend/server.py` or `mcp/server.py`** —
  re-run the `pip install` command in step 1.
- **Python 3.14 release-candidate `TypeError` importing FastAPI** — already handled: both
  `frontend/server.py` and `mcp/server.py` import `frontend/_py314_compat.py` before pulling in
  FastAPI/pydantic, which patches `typing._eval_type` for 3.14 release candidates. No action
  needed.
- **Stale state across runs** — delete the contents of `shared/*/` (or use `/run-pipeline`'s
  clear step, or `POST /clear` on the frontend) to start a demo from a clean slate; the pipeline is
  idempotent either way.
