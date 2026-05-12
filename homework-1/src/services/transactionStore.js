const transactions = [];

function addTransaction(transaction) {
  transactions.push(transaction);
  return transaction;
}

function getTransactions() {
  return transactions;
}

function getTransactionById(id) {
  return transactions.find((transaction) => transaction.id === id) || null;
}

function clearTransactions() {
  transactions.length = 0;
}

module.exports = {
  addTransaction,
  getTransactions,
  getTransactionById,
  clearTransactions,
};
