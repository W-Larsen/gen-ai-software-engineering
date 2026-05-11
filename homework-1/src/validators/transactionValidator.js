const currencyCodes = require("currency-codes");

const ACCOUNT_PATTERN = /^ACC-[A-Za-z0-9]{5}$/;
const ALLOWED_TYPES = new Set(["deposit", "withdrawal", "transfer"]);
const SERVER_MANAGED_FIELDS = ["id", "timestamp", "status"];

const ISO_CURRENCIES = new Set(
  currencyCodes
    .codes()
    .map((code) => code.toUpperCase())
);

function hasMaxTwoDecimals(value) {
  const scaled = value * 100;
  return Math.abs(scaled - Math.round(scaled)) < 1e-9;
}

function isValidDate(value) {
  const date = new Date(value);
  return !Number.isNaN(date.getTime());
}

function parseDateFilter(value, isEndBoundary) {
  if (!value) {
    return null;
  }

  if (!isValidDate(value)) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const suffix = isEndBoundary ? "T23:59:59.999Z" : "T00:00:00.000Z";
    return new Date(`${value}${suffix}`);
  }

  return new Date(value);
}

function validateAccountId(accountId) {
  if (!ACCOUNT_PATTERN.test(accountId)) {
    return {
      field: "accountId",
      message: "Account ID must match ACC-XXXXX where X is alphanumeric",
    };
  }

  return null;
}

function validateTransactionPayload(payload) {
  const details = [];

  SERVER_MANAGED_FIELDS.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(payload, field)) {
      details.push({
        field,
        message: `${field} is server-managed and cannot be provided`,
      });
    }
  });

  if (!payload.fromAccount || typeof payload.fromAccount !== "string") {
    details.push({ field: "fromAccount", message: "fromAccount is required" });
  } else if (!ACCOUNT_PATTERN.test(payload.fromAccount)) {
    details.push({
      field: "fromAccount",
      message: "fromAccount must match ACC-XXXXX where X is alphanumeric",
    });
  }

  if (!payload.toAccount || typeof payload.toAccount !== "string") {
    details.push({ field: "toAccount", message: "toAccount is required" });
  } else if (!ACCOUNT_PATTERN.test(payload.toAccount)) {
    details.push({
      field: "toAccount",
      message: "toAccount must match ACC-XXXXX where X is alphanumeric",
    });
  }

  if (payload.amount === undefined || payload.amount === null || payload.amount === "") {
    details.push({ field: "amount", message: "Amount is required" });
  } else if (typeof payload.amount !== "number" || Number.isNaN(payload.amount)) {
    details.push({ field: "amount", message: "Amount must be a number" });
  } else {
    if (payload.amount <= 0) {
      details.push({ field: "amount", message: "Amount must be a positive number" });
    }

    if (!hasMaxTwoDecimals(payload.amount)) {
      details.push({ field: "amount", message: "Amount must have at most 2 decimal places" });
    }
  }

  if (!payload.currency || typeof payload.currency !== "string") {
    details.push({ field: "currency", message: "currency is required" });
  } else {
    const normalizedCurrency = payload.currency.toUpperCase();
    if (!ISO_CURRENCIES.has(normalizedCurrency)) {
      details.push({ field: "currency", message: "Invalid currency code" });
    }
  }

  if (!payload.type || typeof payload.type !== "string") {
    details.push({ field: "type", message: "type is required" });
  } else if (!ALLOWED_TYPES.has(payload.type)) {
    details.push({
      field: "type",
      message: "type must be one of: deposit, withdrawal, transfer",
    });
  }

  return details;
}

function validateTransactionFilters(query) {
  const details = [];

  if (query.accountId && !ACCOUNT_PATTERN.test(query.accountId)) {
    details.push({
      field: "accountId",
      message: "accountId must match ACC-XXXXX where X is alphanumeric",
    });
  }

  if (query.type && !ALLOWED_TYPES.has(query.type)) {
    details.push({ field: "type", message: "Invalid type filter" });
  }

  if (query.from && !isValidDate(query.from)) {
    details.push({ field: "from", message: "from must be a valid date" });
  }

  if (query.to && !isValidDate(query.to)) {
    details.push({ field: "to", message: "to must be a valid date" });
  }

  if (query.from && query.to && isValidDate(query.from) && isValidDate(query.to)) {
    const fromDate = parseDateFilter(query.from, false);
    const toDate = parseDateFilter(query.to, true);

    if (fromDate > toDate) {
      details.push({ field: "dateRange", message: "from must be before or equal to to" });
    }
  }

  return details;
}

function validateInterestQuery(query) {
  const details = [];

  if (query.rate === undefined) {
    details.push({ field: "rate", message: "rate is required" });
  } else {
    const parsedRate = Number(query.rate);
    if (!Number.isFinite(parsedRate)) {
      details.push({ field: "rate", message: "rate must be a number" });
    } else if (parsedRate < 0) {
      details.push({ field: "rate", message: "rate must be greater than or equal to 0" });
    }
  }

  if (query.days === undefined) {
    details.push({ field: "days", message: "days is required" });
  } else {
    const parsedDays = Number(query.days);
    if (!Number.isFinite(parsedDays)) {
      details.push({ field: "days", message: "days must be a number" });
    } else if (!Number.isInteger(parsedDays)) {
      details.push({ field: "days", message: "days must be an integer" });
    } else if (parsedDays < 0) {
      details.push({ field: "days", message: "days must be greater than or equal to 0" });
    }
  }

  return details;
}

module.exports = {
  ACCOUNT_PATTERN,
  ALLOWED_TYPES,
  parseDateFilter,
  validateAccountId,
  validateInterestQuery,
  validateTransactionPayload,
  validateTransactionFilters,
};
