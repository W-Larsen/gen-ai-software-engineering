# How to Run

## Prerequisites

- **Node.js 18 or newer** (the built-in `node:test` runner is used; no other dependencies).
  Check with:

  ```bash
  node --version
  ```

No `npm install` is required — the app has **zero dependencies**.

## Run the app

From the `homework-4/` directory:

```bash
npm start sum 1 2 3         # -> 6
npm start avg 2 4 6         # -> 4
npm start discount 200 10   # -> 190   (buggy by design; see BUG-002)
npm start calc "2 + 3 * 4"  # -> 14
npm start help              # usage
```

You can also run the entry point directly:

```bash
node src/index.js avg 1 2 3
```

## Run the tests

```bash
npm test
```

### Expected results

| State | `npm test` outcome |
|-------|--------------------|
| **Before** (as shipped) | **2 failing, 2 passing** — the failures demonstrate BUG-001 (`average([])`) and BUG-002 (`applyDiscount`). |
| **After** the pipeline's bug-fixer | **all passing**, plus the additional regression/edge tests the Unit Test Generator adds. |

The red result before fixing is intentional — it is the documented "before" snapshot.

## Reproduce individual issues

```bash
# BUG-001: average of empty list returns NaN
node -e "console.log(require('./src/calc').average([]))"   # NaN

# BUG-002: discount applied as a flat amount
npm start discount 200 10                                  # 190 (should be 180)

# SEC-001: eval-based code execution (benign input shown; do NOT run hostile input)
npm start calc "2 + 3"                                     # 5
```

See [`context/bugs/001/bug-context.md`](context/bugs/001/bug-context.md) for full details.

## Running the agent pipeline (single command)

The entire 4-agent pipeline runs with **one command**:

```bash
npm run pipeline        # or: ./run-pipeline.sh
./run-pipeline.sh --reset   # restore src/ & tests/ to the "before" state first
```

This requires the [`claude` CLI](https://docs.claude.com/en/docs/claude-code) on your
PATH (the agents/skills live in `.claude/agents/` and `.claude/skills/`). The script runs
each stage headless, in order, loading each agent's model and skills automatically:

| # | Stage | How it runs | Output |
|---|-------|-------------|--------|
| 1 | Bug Researcher | inline prompted session | `research/codebase-research.md` |
| 2 | Research Verifier | `--agent research-verifier` (opus) | `research/verified-research.md` |
| 3 | Bug Planner | inline prompted session | `implementation-plan.md` |
| 4 | Bug Fixer | `--agent bug-fixer` (sonnet) | edits `src/` + `fix-summary.md` |
| 5 | Security Verifier | `--agent security-verifier` (opus) | `security-report.md` |
| 6 | Unit Test Generator | `--agent unit-test-generator` (sonnet) | `tests/` + `test-report.md` |

All artifacts are written under `context/bugs/001/` and reference the real files in `src/`
and `tests/`. The script runs every Claude session with `--permission-mode
bypassPermissions` so it can edit files and run tests unattended — run it only in a trusted
local checkout. It prints a per-stage summary and a final `npm test` run at the end.
