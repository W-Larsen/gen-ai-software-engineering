import { TicketCreateSchema, type TicketCreateInput } from "../models/ticket.schema";
import type { ImportResult } from "./types";

export function parseJson(buffer: Buffer): ImportResult {
  let data: unknown;
  try {
    data = JSON.parse(buffer.toString("utf8"));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { total: 0, successful: 0, failed: [{ row: 0, errors: [`malformed json: ${msg}`] }], records: [] };
  }

  let entries: unknown[];
  if (Array.isArray(data)) {
    entries = data;
  } else if (data && typeof data === "object" && Array.isArray((data as { tickets?: unknown[] }).tickets)) {
    entries = (data as { tickets: unknown[] }).tickets;
  } else {
    return {
      total: 0,
      successful: 0,
      failed: [{ row: 0, errors: ["json must be an array or { tickets: [...] } object"] }],
      records: []
    };
  }

  const records: TicketCreateInput[] = [];
  const failed: ImportResult["failed"] = [];

  entries.forEach((entry, idx) => {
    const row = idx + 1;
    if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
      failed.push({ row, errors: ["element must be an object"] });
      return;
    }
    const parsed = TicketCreateSchema.safeParse(entry);
    if (parsed.success) {
      records.push(parsed.data);
    } else {
      failed.push({
        row,
        errors: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`)
      });
    }
  });

  return {
    total: entries.length,
    successful: records.length,
    failed,
    records
  };
}
