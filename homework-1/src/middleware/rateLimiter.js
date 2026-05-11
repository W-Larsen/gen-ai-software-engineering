const { rateLimit } = require("express-rate-limit");

function createRateLimiter(config = {}) {
  const windowMs = config.windowMs ?? 60 * 1000;
  const max = config.max ?? 100;

  return rateLimit({
    windowMs,
    max,
    standardHeaders: true,
    legacyHeaders: false,
    handler: (req, res) => {
      res.status(429).json({ error: "Too many requests" });
    },
  });
}

module.exports = {
  createRateLimiter,
};
