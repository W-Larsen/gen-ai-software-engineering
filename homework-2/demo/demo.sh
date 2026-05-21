#!/usr/bin/env bash
# demo.sh — end-to-end demonstration of the Ticket Support API
#
# Usage (from homework-2 directory):
#   bash demo/demo.sh
#
# The script starts the server, runs requests, then stops it.
# Requires: curl, node/npm

set -euo pipefail

BASE="http://localhost:3000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_PID=""

# ── colours ──────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GREY='\033[0;90m'
NC='\033[0m'

section() { echo -e "\n${CYAN}━━━━  $1  ━━━━${NC}"; }
ok()      { echo -e "${GREEN}✓  $1${NC}"; }
info()    { echo -e "${YELLOW}→  $1${NC}"; }
resp()    { echo -e "${GREY}$1${NC}"; }

# ── server lifecycle ─────────────────────────────────────────────────────────

start_server() {
  info "Starting server..."
  cd "$ROOT_DIR"
  npm run dev >"$ROOT_DIR/.demo-server.log" 2>&1 &
  SERVER_PID=$!

  # Wait for ts-node-dev to finish compiling and print "listening"
  local tries=0
  until grep -q "listening on" "$ROOT_DIR/.demo-server.log" 2>/dev/null; do
    tries=$((tries + 1))
    if [ $tries -ge 60 ]; then
      echo -e "${RED}✗  Server did not start after 60s. Log:${NC}"
      cat "$ROOT_DIR/.demo-server.log"
      exit 1
    fi
    sleep 1
  done

  # Give the TCP socket a moment to be ready after the log line appears
  sleep 1
  ok "Server is up at $BASE (pid $SERVER_PID)"
}

stop_server() {
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    rm -f "$ROOT_DIR/.demo-server.log"
    ok "Server stopped"
  fi
}

trap stop_server EXIT

# ── request helper ────────────────────────────────────────────────────────────
# Prints the curl command, runs it, prints status + raw response body.

req() {
  local label="$1"; shift
  local method="$1"; shift
  local url="$1"; shift
  # remaining args passed straight to curl (headers, data, form fields)

  info "$label"
  echo -e "${GREY}  $method $url${NC}"

  local http_code
  local body
  body=$(curl -s -o /tmp/demo_resp.txt -w "%{http_code}" \
    -X "$method" "$url" "$@") || true
  http_code="$body"
  body=$(cat /tmp/demo_resp.txt)

  echo -e "${GREY}  HTTP $http_code${NC}"
  resp "  $body"
  echo ""

  # expose for callers that need the raw body
  LAST_BODY="$body"
  LAST_HTTP="$http_code"
}

# Minimal sed extraction of a JSON string value — no jq needed.
extract() {
  # extract_field <json> <key>  →  prints the bare string value
  echo "$1" | sed -n "s/.*\"$2\":\s*\"\([^\"]*\)\".*/\1/p" | head -1
}

# ── start ─────────────────────────────────────────────────────────────────────

start_server

# ── 1. Create ticket ──────────────────────────────────────────────────────────

section "1. Create a ticket"

req "POST /tickets — account access issue" POST "$BASE/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "C-001",
    "customer_email": "alice@demo.com",
    "customer_name": "Alice Demo",
    "subject": "Cannot login to my account",
    "description": "I cannot access my account. The password reset link does not arrive in my inbox.",
    "metadata": { "source": "web_form", "browser": "Chrome", "device_type": "desktop" }
  }'

TICKET_ID=$(extract "$LAST_BODY" "id")
ok "Ticket ID: $TICKET_ID"

# ── 2. Get ticket ─────────────────────────────────────────────────────────────

section "2. Get ticket by ID"

req "GET /tickets/:id" GET "$BASE/tickets/$TICKET_ID"

# ── 3. Update ticket ──────────────────────────────────────────────────────────

section "3. Update — assign to agent, set in_progress"

req "PUT /tickets/:id" PUT "$BASE/tickets/$TICKET_ID" \
  -H "Content-Type: application/json" \
  -d '{ "status": "in_progress", "assigned_to": "agent-42", "tags": ["account", "login"] }'

# ── 4. Auto-classify ─────────────────────────────────────────────────────────

section "4. Auto-classify the ticket"

req "POST /tickets/:id/auto-classify" POST "$BASE/tickets/$TICKET_ID/auto-classify"

# ── 5. Create second ticket + list with filters ───────────────────────────────

section "5. Create a billing ticket then filter the list"

req "POST /tickets — billing issue" POST "$BASE/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "C-002",
    "customer_email": "bob@demo.com",
    "customer_name": "Bob Demo",
    "subject": "Refund for wrong invoice",
    "description": "I was overcharged on my last invoice. Please process a refund for the billing error.",
    "category": "billing_question",
    "metadata": { "source": "email" }
  }'

req "GET /tickets (all)" GET "$BASE/tickets"

req "GET /tickets?category=billing_question" GET "$BASE/tickets?category=billing_question"

req "GET /tickets?status=in_progress" GET "$BASE/tickets?status=in_progress"

# ── 6. Resolve ticket ─────────────────────────────────────────────────────────

section "6. Resolve the first ticket"

req "PUT /tickets/:id — status=resolved" PUT "$BASE/tickets/$TICKET_ID" \
  -H "Content-Type: application/json" \
  -d '{ "status": "resolved" }'

# ── 7. Bulk import CSV ────────────────────────────────────────────────────────

section "7. Bulk import from CSV"

req "POST /tickets/import (sample_tickets.csv)" POST "$BASE/tickets/import" \
  -F "file=@${SCRIPT_DIR}/sample_tickets.csv"

# ── 8. Bulk import JSON + autoClassify ───────────────────────────────────────

section "8. Bulk import from JSON with autoClassify=true"

req "POST /tickets/import?autoClassify=true (sample_tickets.json)" \
  POST "$BASE/tickets/import?autoClassify=true" \
  -F "file=@${SCRIPT_DIR}/sample_tickets.json"

# ── 9. Bulk import XML ────────────────────────────────────────────────────────

section "9. Bulk import from XML"

req "POST /tickets/import (sample_tickets.xml)" POST "$BASE/tickets/import" \
  -F "file=@${SCRIPT_DIR}/sample_tickets.xml"

# ── 10. Validation error ──────────────────────────────────────────────────────

section "10. Validation error — invalid email (expect 400)"

req "POST /tickets — bad email" POST "$BASE/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "C-BAD",
    "customer_email": "not-an-email",
    "customer_name": "Bad Actor",
    "subject": "Test",
    "description": "This description is long enough.",
    "metadata": { "source": "api" }
  }'

ok "Got HTTP $LAST_HTTP (expected 400)"

# ── 11. Unsupported format ────────────────────────────────────────────────────

section "11. Unsupported import format (expect 400)"

req "POST /tickets/import — .sh file" POST "$BASE/tickets/import" \
  -F "file=@${SCRIPT_DIR}/demo.sh;type=application/octet-stream"

ok "Got HTTP $LAST_HTTP (expected 400)"

# ── 12. Delete ticket ─────────────────────────────────────────────────────────

section "12. Delete the first ticket"

req "DELETE /tickets/:id" DELETE "$BASE/tickets/$TICKET_ID"

ok "Deleted — now GET should return 404"
req "GET /tickets/:id (after delete)" GET "$BASE/tickets/$TICKET_ID"
ok "Got HTTP $LAST_HTTP (expected 404)"

# ── done ──────────────────────────────────────────────────────────────────────

echo -e "\n${GREEN}━━━━  Demo complete  ━━━━${NC}\n"
