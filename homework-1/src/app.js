const express = require("express");
const transactionsRouter = require("./routes/transactions");
const { createRateLimiter } = require("./middleware/rateLimiter");

function createApp(options = {}) {
  const app = express();

  app.use(createRateLimiter(options.rateLimit));
  app.use(express.json());
  app.use(transactionsRouter);

  app.use((req, res) => {
    res.status(404).json({ error: "Not found" });
  });

  app.use((err, req, res, next) => {
    void err;
    void req;
    void next;
    res.status(500).json({ error: "Internal server error" });
  });

  return app;
}

const app = createApp();

module.exports = app;
module.exports.createApp = createApp;
