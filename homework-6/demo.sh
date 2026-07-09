#!/usr/bin/env bash
#
# demo.sh -- one-command, end-to-end demonstration of the banking transaction-processing pipeline.
#
# Executable equivalent of HOWTORUN.md: provisions a virtualenv, runs the validator dry-run, the
# full CLI pipeline, the pytest coverage gate, the custom MCP tools, and finally the live web
# dashboard -- submitting transactions and watching them animate through validator -> fraud
# detector -> compliance checker. No pipeline logic is reimplemented here; every step shells out to
# an entrypoint that already exists.
#
#   ./demo.sh                 full demo, leaves the dashboard running until Ctrl-C
#   ./demo.sh --exit          full demo, tears the server down and exits (CI-friendly)
#   ./demo.sh --slow          use the real 1-5s per-stage delays instead of the brisk demo delays
#   ./demo.sh --no-tests      skip the pytest + coverage step
#   ./demo.sh --skip-install  assume .venv already has the dependencies
#   ./demo.sh --port 8123     start the dashboard on a specific port
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

PORT=8000
KEEP_OPEN=1
RUN_TESTS=1
SKIP_INSTALL=0
MIN_DELAY=0.3
MAX_DELAY=0.8
RANDOM_COUNT=2
COVERAGE_FLOOR=80
WATCH_TIMEOUT=90
READY_TIMEOUT=25

usage() {
    sed -n '3,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --exit)          KEEP_OPEN=0 ;;
        --keep-open)     KEEP_OPEN=1 ;;
        --no-tests)      RUN_TESTS=0 ;;
        --skip-install)  SKIP_INSTALL=1 ;;
        --slow)          MIN_DELAY=1; MAX_DELAY=5; WATCH_TIMEOUT=180 ;;
        --port)          PORT="${2:?--port needs a number}"; shift ;;
        --port=*)        PORT="${1#*=}" ;;
        -h|--help)       usage ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
    YELLOW=$'\033[33m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
else
    BOLD=''; DIM=''; RED=''; GREEN=''; YELLOW=''; CYAN=''; RESET=''
fi

TOTAL_STEPS=8
step() {
    printf '\n%s%s>> Step %s/%s -- %s%s\n' "$BOLD" "$CYAN" "$1" "$TOTAL_STEPS" "$2" "$RESET"
    printf '%s%s%s\n' "$DIM" "$(printf '%.0s-' {1..76})" "$RESET"
}
run_cmd() { printf '%s$ %s%s\n\n' "$DIM" "$*" "$RESET"; "$@"; }
ok()    { printf '%s  PASS%s  %s\n' "$GREEN" "$RESET" "$1"; }
warn()  { printf '%s  WARN%s  %s\n' "$YELLOW" "$RESET" "$1"; }
die()   { printf '\n%s  FAIL%s  %s\n' "$RED" "$RESET" "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Cleanup: always reap the background uvicorn, however we leave.
# ---------------------------------------------------------------------------

SERVER_PID=""
SERVER_LOG=""
cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        printf '\n%sStopping dashboard (pid %s)...%s\n' "$DIM" "$SERVER_PID" "$RESET"
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    [[ -n "$SERVER_LOG" && -f "$SERVER_LOG" ]] && rm -f "$SERVER_LOG"
    return 0
}
trap cleanup EXIT INT TERM

# ===========================================================================
step 1 "Preflight -- interpreter, version, curl"
# ===========================================================================

BOOT_PY=""
for candidate in python python3; do
    if command -v "$candidate" >/dev/null 2>&1; then BOOT_PY="$candidate"; break; fi
done
if [[ -z "$BOOT_PY" ]] && command -v py >/dev/null 2>&1; then BOOT_PY="py -3"; fi
[[ -n "$BOOT_PY" ]] || die "No Python interpreter found on PATH. Install Python 3.11+ and retry."

$BOOT_PY - <<'PY' || die "Python 3.11+ is required (see HOWTORUN.md step 1)."
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY

command -v curl >/dev/null 2>&1 || die "curl not found on PATH; demo.sh needs it to drive the web UI."

ok "$($BOOT_PY -c 'import sys; print("Python " + sys.version.split()[0])') at $(command -v ${BOOT_PY%% *})"
ok "curl $(curl --version | head -1 | cut -d' ' -f2)"

# ===========================================================================
step 2 "Provision -- .venv + dependencies"
# ===========================================================================

VENV_DIR=".venv"
venv_python() {
    if   [[ -x "$VENV_DIR/bin/python" ]];        then echo "$VENV_DIR/bin/python"
    elif [[ -x "$VENV_DIR/Scripts/python.exe" ]]; then echo "$VENV_DIR/Scripts/python.exe"
    elif [[ -x "$VENV_DIR/Scripts/python" ]];     then echo "$VENV_DIR/Scripts/python"
    fi
}

if [[ -z "$(venv_python)" ]]; then
    printf 'Creating %s (first run only, this takes a moment)...\n' "$VENV_DIR"
    run_cmd $BOOT_PY -m venv "$VENV_DIR"
fi
PY="$(venv_python)"
[[ -n "$PY" ]] || die "Failed to create $VENV_DIR. Delete it and re-run, or use your own venv."
ok "Interpreter: $PY"

deps_present() { "$PY" -c 'import fastapi, uvicorn, pytest, pytest_cov, mcp' >/dev/null 2>&1; }

if [[ "$SKIP_INSTALL" -eq 1 ]]; then
    deps_present || die "--skip-install given but dependencies are missing from $VENV_DIR."
    ok "Dependencies present (install skipped)"
elif deps_present; then
    ok "Dependencies already installed"
else
    printf 'Installing fastapi, uvicorn, pytest, pytest-cov, mcp ...\n'
    "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    run_cmd "$PY" -m pip install --quiet \
        "fastapi>=0.139" "uvicorn>=0.49" "pytest>=9.1" "pytest-cov>=7.1" "mcp>=1.28"
    deps_present || die "Dependency install did not take; see the pip output above."
    ok "Dependencies installed into $VENV_DIR"
fi

# ===========================================================================
step 3 "Clean slate -- wipe shared/ and the audit log"
# ===========================================================================

"$PY" - <<'PY'
import pathlib, shutil
root = pathlib.Path("shared")
removed = 0
for sub in ("input", "processing", "output", "results"):
    d = root / sub
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.json"):
        p.unlink(); removed += 1
logs = pathlib.Path("logs"); logs.mkdir(exist_ok=True)
audit = logs / "audit.log"
if audit.exists():
    audit.write_text("", encoding="utf-8")
print(f"Removed {removed} stale message/result file(s); audit log truncated.")
PY
ok "shared/{input,processing,output,results} and logs/audit.log are empty"

# ===========================================================================
step 4 "Validate only -- agents/transaction_validator.py --dry-run"
# ===========================================================================

run_cmd "$PY" agents/transaction_validator.py --dry-run
ok "Validator reported per-transaction verdicts without writing to shared/"

# ===========================================================================
step 5 "Full pipeline -- integrator.py (validator -> fraud -> compliance)"
# ===========================================================================

run_cmd "$PY" integrator.py

echo
"$PY" - <<'PY'
import json, pathlib
s = json.loads(pathlib.Path("shared/results/summary.json").read_text(encoding="utf-8"))
rows = [
    ("Transactions processed", s["total"]),
    ("Passed validation",      s["validated"]),
    ("Rejected at validation", s["rejected_at_validation"]),
    ("Cleared by compliance",  s["cleared"]),
    ("Flagged for review",     s["flagged"]),
    ("Rejected at compliance", s["rejected_at_compliance"]),
    ("Require regulatory report", s["requires_report"]),
    ("Malformed input records",   s["malformed_input_count"]),
    ("Pipeline errors",           s["error_count"]),
]
width = max(len(k) for k, _ in rows)
for k, v in rows:
    print(f"  {k.ljust(width)}  {v}")
PY
ok "shared/results/ populated ($("$PY" -c 'import pathlib;print(len(list(pathlib.Path("shared/results").glob("TXN*.json"))))') transaction results + summary.json)"

# ===========================================================================
step 6 "Test suite -- the same command the push-time coverage gate runs"
# ===========================================================================

if [[ "$RUN_TESTS" -eq 0 ]]; then
    warn "Skipped (--no-tests)"
else
    set +e
    run_cmd "$PY" -m pytest tests/ --cov=agents --cov=integrator --cov-report=term-missing
    pytest_status=$?
    set -e
    [[ $pytest_status -eq 0 ]] || die "Test suite failed (exit $pytest_status). Demo aborted."

    # Re-derive the TOTAL coverage percentage from the .coverage database written above.
    coverage_pct="$("$PY" - <<'PY'
try:
    from coverage import Coverage
    cov = Coverage()
    cov.load()
    import io
    print(f"{cov.report(file=io.StringIO()):.0f}")
except Exception:
    print("")
PY
)"
    if [[ -n "$coverage_pct" ]]; then
        if [[ "$coverage_pct" -ge "$COVERAGE_FLOOR" ]]; then
            ok "All tests pass; coverage ${coverage_pct}% >= ${COVERAGE_FLOOR}% gate (.claude/hooks/coverage_gate.py)"
        else
            die "Coverage ${coverage_pct}% is below the ${COVERAGE_FLOOR}% gate."
        fi
    else
        ok "All tests pass (see the TOTAL row above for coverage)"
    fi
fi

# ===========================================================================
step 7 "Custom MCP server -- pipeline-status tools, called in-process"
# ===========================================================================

# mcp/ is deliberately not a package (it must not shadow the installed `mcp` SDK), so the module is
# loaded by file path -- exactly as tests/test_mcp_server.py does.
"$PY" - <<'PY'
import importlib.util, json, pathlib

spec = importlib.util.spec_from_file_location(
    "mcp_pipeline_server", pathlib.Path("mcp/server.py").resolve()
)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

print('  get_transaction_status("TXN002"):')
print(json.dumps(server._status_for("TXN002"), indent=2))
print()
listing = server._all_results()
print("  list_pipeline_results():")
print(json.dumps({k: listing[k] for k in ("total", "by_decision", "by_status")}, indent=2))
print()
print("  resource pipeline://summary -> shared/results/summary.json "
      f"({len(server._summary_text())} bytes)")
PY
ok "MCP tools return PII-safe views (no account numbers, names, or descriptions)"

# ===========================================================================
step 8 "Live dashboard -- submit transactions and watch them flow"
# ===========================================================================

PORT="$("$PY" - "$PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
for candidate in range(port, port + 20):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", candidate))
        except OSError:
            continue
    print(candidate)
    break
else:
    sys.exit(1)
PY
)" || die "No free TCP port found near $PORT."

BASE="http://127.0.0.1:$PORT"
SERVER_LOG="$(mktemp -t demo-uvicorn.XXXXXX)"
printf '%s$ %s -m uvicorn frontend.server:app --host 127.0.0.1 --port %s%s\n\n' \
    "$DIM" "$PY" "$PORT" "$RESET"
"$PY" -m uvicorn frontend.server:app --host 127.0.0.1 --port "$PORT" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

ready=0
for _ in $(seq 1 $((READY_TIMEOUT * 4))); do
    if curl -fsS "$BASE/api/status" >/dev/null 2>&1; then ready=1; break; fi
    kill -0 "$SERVER_PID" 2>/dev/null || break
    sleep 0.25
done
if [[ "$ready" -ne 1 ]]; then
    echo "--- uvicorn log ---" >&2
    cat "$SERVER_LOG" >&2
    die "Dashboard never became ready on $BASE"
fi
ok "Dashboard serving at $BASE"

# `/api/status` overlays the live tracker on a file view of shared/. Step 5 already left terminal
# results on disk, so clear them first -- otherwise every transaction reads as already-finished.
curl -fsS -X POST "$BASE/clear" -H 'Content-Type: application/json' >/dev/null
ok "POST /clear -- shared/ wiped so the run animates from scratch"

submitted="$(curl -fsS -X POST "$BASE/submit" -H 'Content-Type: application/json' \
    -d "{\"min_delay\": $MIN_DELAY, \"max_delay\": $MAX_DELAY}")"
random_out="$(curl -fsS -X POST "$BASE/random" -H 'Content-Type: application/json' \
    -d "{\"count\": $RANDOM_COUNT, \"min_delay\": $MIN_DELAY, \"max_delay\": $MAX_DELAY}")"

expected="$("$PY" - "$submitted" "$random_out" <<'PY'
import json, sys
sub = json.loads(sys.argv[1])
rnd = json.loads(sys.argv[2])
ids = list(sub["transaction_ids"]) + [t["transaction_id"] for t in rnd["transactions"]]
print(len(ids))
PY
)"
ok "POST /submit -- $(echo "$submitted" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["submitted"])') sample transactions"
ok "POST /random -- $RANDOM_COUNT generated transactions (exercises the random-schema path)"
printf '\n%sWatching GET /api/status until all %s transactions reach the results stage...%s\n\n' \
    "$DIM" "$expected" "$RESET"

render_table() {
    # Prints the status table; exits 0 only once every expected transaction is terminal.
    "$PY" - "$1" "$2" <<'PY'
import json, sys
entries = json.loads(sys.argv[1])
expected = int(sys.argv[2])

hdr = f"  {'TRANSACTION':<14} {'STAGE':<12} {'OUTCOME':<10} {'RISK':>5}  REASONS"
print(hdr)
print("  " + "-" * (len(hdr) - 2))
for e in sorted(entries, key=lambda e: e["transaction_id"]):
    risk = e.get("risk_score")
    risk = f"{risk}" if risk is not None else "-"
    reasons = ", ".join(e.get("reason") or []) or "-"
    print(f"  {e['transaction_id']:<14} {e['stage']:<12} {e['outcome']:<10} {risk:>5}  {reasons[:34]}")

terminal = [e for e in entries if e["stage"] == "results"]
print(f"\n  {len(terminal)}/{expected} terminal")
sys.exit(0 if len(terminal) >= expected else 1)
PY
}

deadline=$((SECONDS + WATCH_TIMEOUT))
done_all=0
lines_drawn=0
while (( SECONDS < deadline )); do
    status_json="$(curl -fsS "$BASE/api/status" || echo '[]')"

    set +e
    table="$(render_table "$status_json" "$expected")"
    all_terminal=$?
    set -e

    # Redraw in place when interactive; otherwise let each tick stack up in the log.
    if [[ -t 1 && "$lines_drawn" -gt 0 ]]; then
        printf '\033[%sA\033[J' "$lines_drawn"
    fi
    printf '%s\n' "$table"
    lines_drawn=$(( $(printf '%s\n' "$table" | wc -l) ))

    if [[ "$all_terminal" -eq 0 ]]; then done_all=1; break; fi
    sleep 1
done

[[ "$done_all" -eq 1 ]] || die "Transactions did not all reach a terminal stage within ${WATCH_TIMEOUT}s."
ok "Every transaction reached a terminal decision through the real agents"

# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------

printf '\n%s%sFinal outcome%s\n' "$BOLD" "$CYAN" "$RESET"
final_json="$(curl -fsS "$BASE/api/status")"
"$PY" - "$final_json" <<'PY'
import collections, json, sys
entries = json.loads(sys.argv[1])
counts = collections.Counter(e["outcome"] for e in entries)
for outcome, n in sorted(counts.items()):
    print(f"  {outcome:<12} {n}")
flagged = [e for e in entries if e["outcome"] == "flagged"]
report  = [e for e in entries if e.get("requires_report")]
if flagged:
    print("\n  Flagged for manual review: " + ", ".join(e["transaction_id"] for e in flagged))
if report:
    print("  Requires regulatory report: " + ", ".join(e["transaction_id"] for e in report))
PY

printf '\n%s%sAudit trail (last 6 of logs/audit.log)%s\n' "$BOLD" "$CYAN" "$RESET"
"$PY" - <<'PY'
import pathlib
lines = pathlib.Path("logs/audit.log").read_text(encoding="utf-8").splitlines()
for line in lines[-6:]:
    print(f"  {line}")
print(f"\n  ({len(lines)} audit entries this run; accounts are masked as ACC-***####)")
PY

printf '\n%s%sAlso available (Claude Code slash commands, not shell commands)%s\n' \
    "$BOLD" "$CYAN" "$RESET"
printf '  /run-pipeline         clear shared/, run integrator.py, report rejections\n'
printf '  /validate-transactions run the validator dry-run and tabulate the verdicts\n'
printf '  /write-spec           regenerate specification.md from its template\n'

if [[ "$KEEP_OPEN" -eq 1 ]]; then
    printf '\n%s%sDashboard is live at %s -- open it in a browser.%s\n' "$BOLD" "$GREEN" "$BASE" "$RESET"
    printf '%sPress Ctrl-C to stop the server and exit.%s\n' "$DIM" "$RESET"
    wait "$SERVER_PID" 2>/dev/null || true
else
    printf '\n%s%sDemo complete.%s\n' "$BOLD" "$GREEN" "$RESET"
fi
