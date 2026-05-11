function computeAccountAnalytics(transactions, accountId) {
  let balance = 0;
  let totalDeposits = 0;
  let totalWithdrawals = 0;
  let transactionCount = 0;
  let mostRecentTimestamp = null;

  transactions.forEach((transaction) => {
    const isRelated =
      transaction.fromAccount === accountId || transaction.toAccount === accountId;

    if (!isRelated) {
      return;
    }

    transactionCount += 1;

    const timestampMs = new Date(transaction.timestamp).getTime();
    if (
      mostRecentTimestamp === null ||
      timestampMs > new Date(mostRecentTimestamp).getTime()
    ) {
      mostRecentTimestamp = transaction.timestamp;
    }

    if (transaction.type === "deposit" && transaction.toAccount === accountId) {
      balance += transaction.amount;
      totalDeposits += transaction.amount;
      return;
    }

    if (transaction.type === "withdrawal" && transaction.fromAccount === accountId) {
      balance -= transaction.amount;
      totalWithdrawals += transaction.amount;
      return;
    }

    if (transaction.type === "transfer") {
      if (transaction.fromAccount === accountId) {
        balance -= transaction.amount;
        totalWithdrawals += transaction.amount;
      }

      if (transaction.toAccount === accountId) {
        balance += transaction.amount;
        totalDeposits += transaction.amount;
      }
    }
  });

  return {
    balance: Number(balance.toFixed(2)),
    totalDeposits: Number(totalDeposits.toFixed(2)),
    totalWithdrawals: Number(totalWithdrawals.toFixed(2)),
    transactionCount,
    mostRecentTransactionDate: mostRecentTimestamp,
  };
}

module.exports = {
  computeAccountAnalytics,
};
