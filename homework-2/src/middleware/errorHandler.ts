import type { NextFunction, Request, Response } from "express";
import multer from "multer";
import { ZodError } from "zod";
import { HttpError } from "../utils/http";

export function errorHandler(
  err: unknown,
  _req: Request,
  res: Response,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _next: NextFunction
): void {
  if (err instanceof ZodError) {
    res.status(400).json({
      error: "validation_error",
      details: err.issues.map((i) => ({ path: i.path.join("."), message: i.message }))
    });
    return;
  }
  if (err instanceof HttpError) {
    res.status(err.status).json({ error: err.message, details: err.details });
    return;
  }
  if (err instanceof multer.MulterError) {
    res.status(400).json({ error: "upload_error", details: err.message });
    return;
  }
  const message = err instanceof Error ? err.message : "internal_error";
  res.status(500).json({ error: "internal_error", details: message });
}
