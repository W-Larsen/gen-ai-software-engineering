import { parse } from "csv-parse/sync";
import { TicketCreateSchema, type TicketCreateInput } from "../models/ticket.schema";
import type { ImportResult } from "./types";

export function parseCsv(buffer: Buffer): ImportResult {
  let rows: Record<string, string>[];
  try {
    rows = parse(buffer, {
      columns: true,
      trim: true,
      skip_empty_lines: true,
      relax_column_count: false
    }) as Record<string, string>[];
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { total: 0, successful: 0, failed: [{ row: 0, errors: [`malformed csv: ${msg}`] }], records: [] };
  }

  const records: TicketCreateInput[] = [];
  const failed: ImportResult["failed"] = [];

  rows.forEach((raw, idx) => {
    const row = idx + 2; // header is row 1
    const candidate = normalizeRow(raw);
    const parsed = TicketCreateSchema.safeParse(candidate);
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
    total: rows.length,
    successful: records.length,
    failed,
    records
  };
}

function normalizeRow(raw: Record<string, string>): Record<string, unknown> {
  const tags = raw.tags
    ? raw.tags.split(",").map((t) => t.trim()).filter(Boolean)
    : [];
  const metadata: Record<string, unknown> = {
    source: raw["metadata.source"] || raw.source
  };
  const browser = raw["metadata.browser"] || raw.browser;
  if (browser) metadata.browser = browser;
  const device = raw["metadata.device_type"] || raw.device_type;
  if (device) metadata.device_type = device;

  return {
    customer_id: raw.customer_id,
    customer_email: raw.customer_email,
    customer_name: raw.customer_name,
    subject: raw.subject,
    description: raw.description,
    category: raw.category || undefined,
    priority: raw.priority || undefined,
    status: raw.status || undefined,
    assigned_to: raw.assigned_to || undefined,
    tags,
    metadata
  };
}
