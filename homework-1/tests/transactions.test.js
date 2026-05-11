const request = require("supertest");
const app = require("../src/app");
const { createApp } = require("../src/app");
const {
  addTransaction,
  clearTransactions,
} = require("../src/services/transactionStore");

const VALID_PAYLOAD = {
  fromAccount: "ACC-A1B2C",
  toAccount: "ACC-D3E4F",
  amount: 100.5,
  currency: "USD",
  type: "transfer",
};

describe("Task 1: Core API implementation", () => {
  beforeEach(() => {
    clearTransactions();
  });

  test("POST /transactions creates a transaction with server-managed fields", async () => {
    const response = await request(app)
      .post("/transactions")
      .send(VALID_PAYLOAD)
      .expect(201);

    expect(response.body).toMatchObject({
      ...VALID_PAYLOAD,
      currency: "USD",
      status: "completed",
    });
    expect(response.body.id).toEqual(expect.any(String));
    expect(response.body.timestamp).toEqual(expect.any(String));
    expect(new Date(response.body.timestamp).toISOString()).toBe(response.body.timestamp);
  });

  test("GET /transactions returns all transactions", async () => {
    await request(app).post("/transactions").send(VALID_PAYLOAD).expect(201);

    const response = await request(app).get("/transactions").expect(200);
    expect(response.body).toHaveLength(1);
    expect(response.body[0].fromAccount).toBe("ACC-A1B2C");
  });

  test("GET /transactions/:id returns transaction and 404 for missing id", async () => {
    const createResponse = await request(app)
      .post("/transactions")
      .send(VALID_PAYLOAD)
      .expect(201);

    const foundResponse = await request(app)
      .get(`/transactions/${createResponse.body.id}`)
      .expect(200);

    expect(foundResponse.body.id).toBe(createResponse.body.id);

    await request(app).get("/transactions/non-existent-id").expect(404);
  });

  test("GET /accounts/:accountId/balance computes balance using standard ledger rules", async () => {
    addTransaction({
      id: "t1",
      fromAccount: "ACC-ZZZ11",
      toAccount: "ACC-A1B2C",
      amount: 200,
      currency: "USD",
      type: "deposit",
      timestamp: "2024-01-10T10:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "t2",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-YYY22",
      amount: 50,
      currency: "USD",
      type: "withdrawal",
      timestamp: "2024-01-11T10:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "t3",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-D3E4F",
      amount: 30,
      currency: "USD",
      type: "transfer",
      timestamp: "2024-01-12T10:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "t4",
      fromAccount: "ACC-QQQ44",
      toAccount: "ACC-A1B2C",
      amount: 20,
      currency: "USD",
      type: "transfer",
      timestamp: "2024-01-13T10:00:00.000Z",
      status: "completed",
    });

    const response = await request(app).get("/accounts/ACC-A1B2C/balance").expect(200);

    expect(response.body).toEqual({
      accountId: "ACC-A1B2C",
      balance: 140,
    });
  });
});

describe("Task 2: Transaction validation", () => {
  beforeEach(() => {
    clearTransactions();
  });

  test("rejects non-positive amount and more than 2 decimal places", async () => {
    const response = await request(app)
      .post("/transactions")
      .send({
        ...VALID_PAYLOAD,
        amount: -1.123,
      })
      .expect(400);

    expect(response.body.error).toBe("Validation failed");
    expect(response.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "amount", message: "Amount must be a positive number" }),
        expect.objectContaining({ field: "amount", message: "Amount must have at most 2 decimal places" }),
      ])
    );
  });

  test("rejects malformed account numbers", async () => {
    const response = await request(app)
      .post("/transactions")
      .send({
        ...VALID_PAYLOAD,
        fromAccount: "BAD-123",
        toAccount: "ACC-12",
      })
      .expect(400);

    expect(response.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "fromAccount" }),
        expect.objectContaining({ field: "toAccount" }),
      ])
    );
  });

  test("rejects invalid currency code", async () => {
    const response = await request(app)
      .post("/transactions")
      .send({
        ...VALID_PAYLOAD,
        currency: "ZZZ",
      })
      .expect(400);

    expect(response.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "currency", message: "Invalid currency code" }),
      ])
    );
  });

  test("rejects invalid transaction type", async () => {
    const response = await request(app)
      .post("/transactions")
      .send({
        ...VALID_PAYLOAD,
        type: "payment",
      })
      .expect(400);

    expect(response.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "type" }),
      ])
    );
  });

  test("rejects client-supplied server-managed fields", async () => {
    const response = await request(app)
      .post("/transactions")
      .send({
        ...VALID_PAYLOAD,
        id: "custom-id",
        timestamp: "2024-01-01T00:00:00.000Z",
        status: "pending",
      })
      .expect(400);

    expect(response.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "id" }),
        expect.objectContaining({ field: "timestamp" }),
        expect.objectContaining({ field: "status" }),
      ])
    );
  });
});

describe("Task 3: Basic transaction history filters", () => {
  beforeEach(() => {
    clearTransactions();

    addTransaction({
      id: "tx-1",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-D3E4F",
      amount: 10,
      currency: "USD",
      type: "transfer",
      timestamp: "2024-01-05T09:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "tx-2",
      fromAccount: "ACC-QQQ11",
      toAccount: "ACC-A1B2C",
      amount: 20,
      currency: "EUR",
      type: "deposit",
      timestamp: "2024-01-15T09:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "tx-3",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-RRR22",
      amount: 30,
      currency: "GBP",
      type: "withdrawal",
      timestamp: "2024-01-25T09:00:00.000Z",
      status: "completed",
    });
  });

  test("filters by accountId", async () => {
    const response = await request(app)
      .get("/transactions")
      .query({ accountId: "ACC-D3E4F" })
      .expect(200);

    expect(response.body).toHaveLength(1);
    expect(response.body[0].id).toBe("tx-1");
  });

  test("filters by type", async () => {
    const response = await request(app)
      .get("/transactions")
      .query({ type: "deposit" })
      .expect(200);

    expect(response.body).toHaveLength(1);
    expect(response.body[0].id).toBe("tx-2");
  });

  test("filters by date range inclusively", async () => {
    const response = await request(app)
      .get("/transactions")
      .query({ from: "2024-01-15", to: "2024-01-25" })
      .expect(200);

    expect(response.body.map((item) => item.id)).toEqual(["tx-2", "tx-3"]);
  });

  test("combines multiple filters", async () => {
    const response = await request(app)
      .get("/transactions")
      .query({
        accountId: "ACC-A1B2C",
        type: "withdrawal",
        from: "2024-01-01",
        to: "2024-01-31",
      })
      .expect(200);

    expect(response.body).toHaveLength(1);
    expect(response.body[0].id).toBe("tx-3");
  });

  test("returns 400 for invalid from/to filters", async () => {
    const invalidFromResponse = await request(app)
      .get("/transactions")
      .query({ from: "not-a-date" })
      .expect(400);

    expect(invalidFromResponse.body.details).toEqual(
      expect.arrayContaining([expect.objectContaining({ field: "from" })])
    );

    const invalidRangeResponse = await request(app)
      .get("/transactions")
      .query({ from: "2024-02-01", to: "2024-01-01" })
      .expect(400);

    expect(invalidRangeResponse.body.details).toEqual(
      expect.arrayContaining([expect.objectContaining({ field: "dateRange" })])
    );
  });
});

describe("Task 4 Option A: account summary endpoint", () => {
  beforeEach(() => {
    clearTransactions();
  });

  test("returns summary with inflow/outflow totals, count, and most recent date", async () => {
    addTransaction({
      id: "s-1",
      fromAccount: "ACC-ZZZ11",
      toAccount: "ACC-A1B2C",
      amount: 100,
      currency: "USD",
      type: "deposit",
      timestamp: "2024-01-05T08:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "s-2",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-YYY22",
      amount: 25,
      currency: "USD",
      type: "withdrawal",
      timestamp: "2024-01-10T08:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "s-3",
      fromAccount: "ACC-QQQ44",
      toAccount: "ACC-A1B2C",
      amount: 40,
      currency: "USD",
      type: "transfer",
      timestamp: "2024-01-15T08:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "s-4",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-RRR55",
      amount: 10,
      currency: "USD",
      type: "transfer",
      timestamp: "2024-01-20T08:00:00.000Z",
      status: "completed",
    });
    addTransaction({
      id: "s-5",
      fromAccount: "ACC-FFF66",
      toAccount: "ACC-GGG77",
      amount: 999,
      currency: "USD",
      type: "transfer",
      timestamp: "2024-01-21T08:00:00.000Z",
      status: "completed",
    });

    const response = await request(app).get("/accounts/ACC-A1B2C/summary").expect(200);

    expect(response.body).toEqual({
      accountId: "ACC-A1B2C",
      totalDeposits: 140,
      totalWithdrawals: 35,
      transactionCount: 4,
      mostRecentTransactionDate: "2024-01-20T08:00:00.000Z",
    });
  });

  test("returns zero/null summary for account with no transactions", async () => {
    const response = await request(app).get("/accounts/ACC-NONE1/summary").expect(200);

    expect(response.body).toEqual({
      accountId: "ACC-NONE1",
      totalDeposits: 0,
      totalWithdrawals: 0,
      transactionCount: 0,
      mostRecentTransactionDate: null,
    });
  });

  test("returns 400 for invalid account format", async () => {
    const response = await request(app).get("/accounts/INVALID/summary").expect(400);

    expect(response.body.error).toBe("Validation failed");
    expect(response.body.details).toEqual(
      expect.arrayContaining([expect.objectContaining({ field: "accountId" })])
    );
  });
});

describe("Task 4 Option B: simple interest endpoint", () => {
  beforeEach(() => {
    clearTransactions();
  });

  test("calculates simple interest for positive balance", async () => {
    addTransaction({
      id: "i-1",
      fromAccount: "ACC-SRC01",
      toAccount: "ACC-A1B2C",
      amount: 365,
      currency: "USD",
      type: "deposit",
      timestamp: "2024-01-05T08:00:00.000Z",
      status: "completed",
    });

    const response = await request(app)
      .get("/accounts/ACC-A1B2C/interest")
      .query({ rate: "0.1", days: "30" })
      .expect(200);

    expect(response.body).toEqual({
      accountId: "ACC-A1B2C",
      principal: 365,
      rate: 0.1,
      days: 30,
      interest: 3,
    });
  });

  test("calculates negative interest for negative balance", async () => {
    addTransaction({
      id: "i-2",
      fromAccount: "ACC-A1B2C",
      toAccount: "ACC-SRC01",
      amount: 365,
      currency: "USD",
      type: "withdrawal",
      timestamp: "2024-01-05T08:00:00.000Z",
      status: "completed",
    });

    const response = await request(app)
      .get("/accounts/ACC-A1B2C/interest")
      .query({ rate: "0.1", days: "30" })
      .expect(200);

    expect(response.body.interest).toBe(-3);
    expect(response.body.principal).toBe(-365);
  });

  test("returns zero interest for empty account", async () => {
    const response = await request(app)
      .get("/accounts/ACC-EMPT1/interest")
      .query({ rate: "0.25", days: "100" })
      .expect(200);

    expect(response.body).toEqual({
      accountId: "ACC-EMPT1",
      principal: 0,
      rate: 0.25,
      days: 100,
      interest: 0,
    });
  });

  test("returns 400 for invalid interest query values", async () => {
    const missingParams = await request(app)
      .get("/accounts/ACC-A1B2C/interest")
      .expect(400);
    expect(missingParams.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "rate" }),
        expect.objectContaining({ field: "days" }),
      ])
    );

    const invalidParams = await request(app)
      .get("/accounts/ACC-A1B2C/interest")
      .query({ rate: "-0.1", days: "1.5" })
      .expect(400);
    expect(invalidParams.body.details).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "rate" }),
        expect.objectContaining({ field: "days" }),
      ])
    );
  });
});

describe("Task 4 Option D: rate limiting", () => {
  beforeEach(() => {
    clearTransactions();
  });

  test("returns 429 after exceeding max requests per minute", async () => {
    const limitedApp = createApp({
      rateLimit: { windowMs: 60 * 1000, max: 5 },
    });

    for (let index = 0; index < 5; index += 1) {
      await request(limitedApp).get("/transactions").expect(200);
    }

    const limitedResponse = await request(limitedApp).get("/transactions").expect(429);
    expect(limitedResponse.body).toEqual({ error: "Too many requests" });
  });

  test("applies globally across existing and new endpoints", async () => {
    const limitedApp = createApp({
      rateLimit: { windowMs: 60 * 1000, max: 3 },
    });

    await request(limitedApp).get("/transactions").expect(200);
    await request(limitedApp).get("/accounts/ACC-A1B2C/summary").expect(200);
    await request(limitedApp)
      .get("/accounts/ACC-A1B2C/interest")
      .query({ rate: "0", days: "0" })
      .expect(200);

    await request(limitedApp).get("/accounts/ACC-A1B2C/balance").expect(429);
  });
});
