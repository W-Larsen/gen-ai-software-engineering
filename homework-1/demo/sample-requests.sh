#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FILE="$SCRIPT_DIR/sample-data.json"
BASE_URL="${BASE_URL:-http://localhost:3000}"

json_from_file() {
  local key="$1"
  node -e '
    const fs = require("fs");
    const filePath = process.argv[1];
    const key = process.argv[2];
    const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
    process.stdout.write(JSON.stringify(data[key]));
  ' "$DATA_FILE" "$key"
}

echo "Using API base URL: $BASE_URL"

echo "\n1) Create transaction A"
curl -sS -X POST "$BASE_URL/transactions" \
  -H "Content-Type: application/json" \
  -d "$(json_from_file transactionA)"

echo "\n\n2) Create transaction B"
curl -sS -X POST "$BASE_URL/transactions" \
  -H "Content-Type: application/json" \
  -d "$(json_from_file transactionB)"

echo "\n\n3) Create transaction C"
curl -sS -X POST "$BASE_URL/transactions" \
  -H "Content-Type: application/json" \
  -d "$(json_from_file transactionC)"

echo "\n\n4) Get all transactions"
curl -sS "$BASE_URL/transactions"

echo "\n\n5) Filter by account"
curl -sS "$BASE_URL/transactions?accountId=ACC-12345"

echo "\n\n6) Get account balance"
curl -sS "$BASE_URL/accounts/ACC-12345/balance"

echo "\n\n7) Get account summary"
curl -sS "$BASE_URL/accounts/ACC-12345/summary"

echo "\n\n8) Get simple interest"
rate=$(node -e 'const d=require(process.argv[1]); process.stdout.write(String(d.interestQuery.rate));' "$DATA_FILE")
days=$(node -e 'const d=require(process.argv[1]); process.stdout.write(String(d.interestQuery.days));' "$DATA_FILE")
curl -sS "$BASE_URL/accounts/ACC-12345/interest?rate=${rate}&days=${days}"

echo "\n\nDone."
