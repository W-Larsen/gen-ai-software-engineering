import { XMLParser, XMLValidator } from "fast-xml-parser";
import { TicketCreateSchema, type TicketCreateInput } from "../models/ticket.schema";
import type { ImportResult } from "./types";

const parser = new XMLParser({
  ignoreAttributes: false,
  trimValues: true,
  parseTagValue: false,
  parseAttributeValue: false
});

export function parseXml(buffer: Buffer): ImportResult {
  const text = buffer.toString("utf8");
  const validation = XMLValidator.validate(text);
  if (validation !== true) {
    return {
      total: 0,
      successful: 0,
      failed: [{ row: 0, errors: [`malformed xml: ${validation.err.msg}`] }],
      records: []
    };
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = parser.parse(text) as Record<string, unknown>;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return { total: 0, successful: 0, failed: [{ row: 0, errors: [`malformed xml: ${msg}`] }], records: [] };
  }

  const tickets = parsed.tickets as { ticket?: unknown } | undefined;
  if (!tickets || tickets.ticket === undefined) {
    return {
      total: 0,
      successful: 0,
      failed: [{ row: 0, errors: ["xml must contain <tickets><ticket>...</ticket></tickets>"] }],
      records: []
    };
  }

  const raw = Array.isArray(tickets.ticket) ? tickets.ticket : [tickets.ticket];
  const records: TicketCreateInput[] = [];
  const failed: ImportResult["failed"] = [];

  raw.forEach((entry, idx) => {
    const row = idx + 1;
    if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
      failed.push({ row, errors: ["ticket element must be an object"] });
      return;
    }
    const candidate = normalizeTicket(entry as Record<string, unknown>);
    const parsedTicket = TicketCreateSchema.safeParse(candidate);
    if (parsedTicket.success) {
      records.push(parsedTicket.data);
    } else {
      failed.push({
        row,
        errors: parsedTicket.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`)
      });
    }
  });

  return { total: raw.length, successful: records.length, failed, records };
}

function normalizeTicket(raw: Record<string, unknown>): Record<string, unknown> {
  const tagsNode = raw.tags as { tag?: unknown } | undefined;
  let tags: string[] = [];
  if (tagsNode && tagsNode.tag !== undefined) {
    const arr = Array.isArray(tagsNode.tag) ? tagsNode.tag : [tagsNode.tag];
    tags = arr.filter((v) => v !== undefined && v !== null).map((v) => String(v));
  }

  const metadataNode = (raw.metadata ?? {}) as Record<string, unknown>;
  const metadata: Record<string, unknown> = {
    source: metadataNode.source
  };
  if (metadataNode.browser !== undefined) metadata.browser = metadataNode.browser;
  if (metadataNode.device_type !== undefined) metadata.device_type = metadataNode.device_type;

  return {
    customer_id: raw.customer_id,
    customer_email: raw.customer_email,
    customer_name: raw.customer_name,
    subject: raw.subject,
    description: raw.description,
    category: raw.category,
    priority: raw.priority,
    status: raw.status,
    assigned_to: raw.assigned_to,
    tags,
    metadata
  };
}
