import express, { type Express } from "express";
import { ticketsRouter } from "./routes/tickets";
import { errorHandler } from "./middleware/errorHandler";

export function createApp(): Express {
  const app = express();
  app.use(express.json({ limit: "5mb" }));
  app.get("/health", (_req, res) => res.json({ ok: true }));
  app.use("/tickets", ticketsRouter);
  app.use(errorHandler);
  return app;
}
