const express = require("express");
const { randomUUID } = require("crypto");
const {
  addTransaction,
  getTransactions,
  getTransactionById,
} = require("../services/transactionStore");
const { computeAccountAnalytics } = require("../services/accountAnalytics");
const {
  parseDateFilter,
  validateAccountId,
  validateInterestQuery,
  validateTransactionPayload,
  validateTransactionFilters,
} = require("../validators/transactionValidator");

const router = express.Router();

function applyTransactionFilters(transactions, query) {
  return transactions.filter((transaction) => {
    const transactionDate = new Date(transaction.timestamp);

    if (
      query.accountId &&
      transaction.fromAccount !== query.accountId &&
      transaction.toAccount !== query.accountId
    ) {
      return false;
    }

    if (query.type && transaction.type !== query.type) {
      return false;
    }

    if (query.from) {
      const fromDate = parseDateFilter(query.from, false);
      if (transactionDate < fromDate) {
        return false;
      }
    }

    if (query.to) {
      const toDate = parseDateFilter(query.to, true);
      if (transactionDate > toDate) {
        return false;
      }
    }

    return true;
  });
}

router.post("/transactions", (req, res) => {
  const details = validateTransactionPayload(req.body || {});

  if (details.length > 0) {
    return res.status(400).json({
      error: "Validation failed",
      details,
    });
  }

  const transaction = {
    id: randomUUID(),
    fromAccount: req.body.fromAccount,
    toAccount: req.body.toAccount,
    amount: req.body.amount,
    currency: req.body.currency.toUpperCase(),
    type: req.body.type,
    timestamp: new Date().toISOString(),
    status: "completed",
  };

  addTransaction(transaction);

  return res.status(201).json(transaction);
});

router.get("/transactions", (req, res) => {
  const details = validateTransactionFilters(req.query);

  if (details.length > 0) {
    return res.status(400).json({
      error: "Validation failed",
      details,
    });
  }

  const transactions = getTransactions();
  const filteredTransactions = applyTransactionFilters(transactions, req.query);

  return res.status(200).json(filteredTransactions);
});

router.get("/transactions/:id", (req, res) => {
  const transaction = getTransactionById(req.params.id);

  if (!transaction) {
    return res.status(404).json({ error: "Transaction not found" });
  }

  return res.status(200).json(transaction);
});

router.get("/accounts/:accountId/balance", (req, res) => {
  const accountError = validateAccountId(req.params.accountId);

  if (accountError) {
    return res.status(400).json({
      error: "Validation failed",
      details: [accountError],
    });
  }

  const accountId = req.params.accountId;
  const { balance } = computeAccountAnalytics(getTransactions(), accountId);

  return res.status(200).json({
    accountId,
    balance,
  });
});

router.get("/accounts/:accountId/summary", (req, res) => {
  const accountError = validateAccountId(req.params.accountId);

  if (accountError) {
    return res.status(400).json({
      error: "Validation failed",
      details: [accountError],
    });
  }

  const accountId = req.params.accountId;
  const analytics = computeAccountAnalytics(getTransactions(), accountId);

  return res.status(200).json({
    accountId,
    totalDeposits: analytics.totalDeposits,
    totalWithdrawals: analytics.totalWithdrawals,
    transactionCount: analytics.transactionCount,
    mostRecentTransactionDate: analytics.mostRecentTransactionDate,
  });
});

router.get("/accounts/:accountId/interest", (req, res) => {
  const accountError = validateAccountId(req.params.accountId);
  const queryDetails = validateInterestQuery(req.query);
  const details = accountError ? [accountError, ...queryDetails] : queryDetails;

  if (details.length > 0) {
    return res.status(400).json({
      error: "Validation failed",
      details,
    });
  }

  const accountId = req.params.accountId;
  const rate = Number(req.query.rate);
  const days = Number(req.query.days);
  const { balance } = computeAccountAnalytics(getTransactions(), accountId);
  const interest = Number((balance * rate * (days / 365)).toFixed(2));

  return res.status(200).json({
    accountId,
    principal: balance,
    rate,
    days,
    interest,
  });
});

module.exports = router;
