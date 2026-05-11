# ▶️ How to Run the Application

## 1. Prerequisites

- Node.js 18+ (Node.js 20+ recommended)
- npm

## 2. Install Dependencies

From the project root:

```bash
npm install
```

## 3. Run the API

Start server in production mode:

```bash
npm start
```

Server will run on:

```text
http://localhost:3000
```

Run in development mode (auto-restart on file changes):

```bash
npm run dev
```

## 4. Run Tests

```bash
npm test
```

## 5. Demo Scripts (Recommended)

This project includes ready-to-use demo files in `demo/`.

Start app via demo script:

```bash
./demo/run.sh
```

Run sample requests in a second terminal:

```bash
./demo/sample-requests.sh
```

If your API runs on a different host/port:

```bash
BASE_URL=http://localhost:3000 ./demo/sample-requests.sh
```

For VS Code REST Client, use:

- `demo/sample-requests.http`

Reusable request payloads are stored in:

- `demo/sample-data.json`

## 6. Quick API Check (Optional)

Create transaction:

```bash
curl -X POST http://localhost:3000/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "fromAccount": "ACC-12345",
    "toAccount": "ACC-67890",
    "amount": 100.50,
    "currency": "USD",
    "type": "transfer"
  }'
```

Get all transactions:

```bash
curl http://localhost:3000/transactions
```

Get account balance:

```bash
curl http://localhost:3000/accounts/ACC-12345/balance
```
