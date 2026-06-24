#!/usr/bin/env bash
#
# run-pipeline.sh — Single-command runner for the 4-agent bug-fix pipeline.
#
# Runs every stage in the correct order, headless, against the sample app in
# src/. Each stage is a Claude Code session: the four required agents are
# invoked via `--agent <name>` (so they use the model + tools + skills declared
# in their .claude/agents/*.md frontmatter), and the two feeder stages
# (Bug Researcher, Bug Planner) run as plain prompted sessions.
#
#   Bug Researcher  ─▶ research/codebase-research.md
#   Research Verifier (agent) ─▶ research/verified-research.md   [opus]
#   Bug Planner     ─▶ implementation-plan.md
#   Bug Fixer (agent) ─▶ edits src/ + fix-summary.md             [sonnet]
#   Security Verifier (agent) ─▶ security-report.md              [opus]
#   Unit Test Generator (agent) ─▶ tests/ + test-report.md       [sonnet]
#
# Usage:
#   ./run-pipeline.sh            # run the full pipeline
#   ./run-pipeline.sh --reset    # restore src/ & tests/ to the "before" state first
#
# Requirements: the `claude` CLI (Claude Code) on PATH, and Node.js 18+.
#
set -euo pipefail

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

BUG_DIR="context/bugs/001"
RESEARCH_DIR="$BUG_DIR/research"

# Flags passed to every Claude Code session. The pipeline is unattended, so we
# skip interactive permission prompts. Run it in a trusted/local checkout only.
CLAUDE_FLAGS=(--print --permission-mode bypassPermissions)

bold()  { printf '\033[1m%s\033[0m\n' "$1"; }
green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }

# ----------------------------------------------------------------------------
# Preconditions
# ----------------------------------------------------------------------------
if ! command -v claude >/dev/null 2>&1; then
  red "ERROR: the 'claude' CLI is not on PATH. Install Claude Code first."
  exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  red "ERROR: Node.js 18+ is required to run the sample app's tests."
  exit 1
fi

# Optional: restore the seeded "before" state so the run is reproducible.
if [[ "${1:-}" == "--reset" ]]; then
  bold "↺ Resetting src/ and tests/ to the committed 'before' state…"
  git checkout -- src/ tests/ 2>/dev/null || true
fi

mkdir -p "$RESEARCH_DIR"

STAGE=0
TOTAL=6
START_TS=$(date +%s)

# run_stage <title> <agent-or-"-"> <prompt>
# Pass "-" as the agent for the inline feeder stages (no dedicated agent).
run_stage() {
  local title="$1" agent="$2" prompt="$3"
  STAGE=$((STAGE + 1))
  echo
  bold "──────────────────────────────────────────────────────────────"
  bold "  Stage $STAGE/$TOTAL — $title"
  [[ "$agent" != "-" ]] && echo "  agent: $agent" || echo "  mode:  inline prompted session"
  bold "──────────────────────────────────────────────────────────────"

  local stage_start; stage_start=$(date +%s)
  if [[ "$agent" == "-" ]]; then
    claude "${CLAUDE_FLAGS[@]}" "$prompt"
  else
    claude "${CLAUDE_FLAGS[@]}" --agent "$agent" "$prompt"
  fi
  local stage_end; stage_end=$(date +%s)
  green "  ✓ Stage $STAGE done in $((stage_end - stage_start))s"
}

bold "🤖 Starting the 4-agent bug-fix pipeline on the ledger-cli sample app"
echo "   repo: $REPO_ROOT"
echo "   artifacts: $BUG_DIR/"

# ----------------------------------------------------------------------------
# Stage 1 — Bug Researcher (inline; feeds the Research Verifier)
# ----------------------------------------------------------------------------
run_stage "Bug Researcher" "-" \
"You are a Bug Researcher. Read $BUG_DIR/bug-context.md for the brief, then read the \
actual source in src/ and tests/. Produce a research report at \
$RESEARCH_DIR/codebase-research.md that documents each issue (BUG-001, BUG-002, SEC-001) \
with EXACT file:line references and VERBATIM code snippets copied from the current files, \
the root cause, and the proposed fix direction. Verify every line number against the file \
you actually read. Do NOT modify any source code — research only."

# ----------------------------------------------------------------------------
# Stage 2 — Research Verifier (agent, opus)
# ----------------------------------------------------------------------------
run_stage "Research Verifier" "research-verifier" \
"The Bug Researcher's artifact is at $RESEARCH_DIR/codebase-research.md. Independently \
verify every file:line reference and code snippet against the real source in src/ and \
tests/. Use the 'research-quality-measurement' skill (.claude/skills/research-quality-measurement.md) \
for the quality rubric and the required result-file format. Write your verification to \
$RESEARCH_DIR/verified-research.md. Never edit the research file or any source code."

# ----------------------------------------------------------------------------
# Stage 3 — Bug Planner (inline; feeds the Bug Fixer)
# ----------------------------------------------------------------------------
run_stage "Bug Planner" "-" \
"You are a Bug Planner. Using $RESEARCH_DIR/verified-research.md and \
$RESEARCH_DIR/codebase-research.md, write an implementation plan to \
$BUG_DIR/implementation-plan.md. For EACH issue (BUG-001, BUG-002, SEC-001) specify: the \
file path, the exact location, the exact BEFORE code and the exact AFTER code, and the \
test command 'npm test'. The SEC-001 fix MUST replace eval() in src/evaluate.js with a \
safe parser that only allows numbers and the operators + - * / ( ). Do NOT modify any \
source code yet — write the plan only."

# ----------------------------------------------------------------------------
# Stage 4 — Bug Fixer (agent, sonnet)
# ----------------------------------------------------------------------------
run_stage "Bug Fixer" "bug-fixer" \
"Execute the implementation plan at $BUG_DIR/implementation-plan.md. Apply each change to \
the files in src/, run 'npm test' after each change, and write a fix summary to \
$BUG_DIR/fix-summary.md following your required structure. Stop and document if a test \
fails or the actual code does not match the plan's before-snippet."

# ----------------------------------------------------------------------------
# Stage 5 — Security Verifier (agent, opus)
# ----------------------------------------------------------------------------
run_stage "Security Verifier" "security-verifier" \
"Perform a security review of the changed code. Read $BUG_DIR/fix-summary.md first, then \
review the changed files (use 'git diff' / 'git status' to identify them). Scan for \
injection, hardcoded secrets, insecure comparisons, missing validation, unsafe deps, and \
XSS/CSRF where relevant. Confirm SEC-001 (eval) is genuinely remediated. Write your report \
to $BUG_DIR/security-report.md. Do NOT edit any code — the report is your only output."

# ----------------------------------------------------------------------------
# Stage 6 — Unit Test Generator (agent, sonnet)
# ----------------------------------------------------------------------------
run_stage "Unit Test Generator" "unit-test-generator" \
"Generate and run unit tests for the changed code only. Read $BUG_DIR/fix-summary.md and \
the changed files (use 'git diff'). Follow the 'unit-tests-FIRST' skill \
(.claude/skills/unit-tests-FIRST.md): every test must satisfy all five FIRST principles. \
Match the project's existing test framework (node:test under tests/). Include a regression \
test for each fixed bug. Run 'npm test', capture the real results, and write \
$BUG_DIR/test-report.md in the format the skill defines."

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
END_TS=$(date +%s)
echo
bold "══════════════════════════════════════════════════════════════"
green "✓ Pipeline complete in $((END_TS - START_TS))s"
bold "══════════════════════════════════════════════════════════════"
echo "Artifacts written under $BUG_DIR/:"
for f in \
  "$RESEARCH_DIR/codebase-research.md" \
  "$RESEARCH_DIR/verified-research.md" \
  "$BUG_DIR/implementation-plan.md" \
  "$BUG_DIR/fix-summary.md" \
  "$BUG_DIR/security-report.md" \
  "$BUG_DIR/test-report.md"; do
  if [[ -f "$f" ]]; then green "  ✓ $f"; else red "  ✗ $f (missing)"; fi
done
echo
bold "Final test run:"
npm test || true
