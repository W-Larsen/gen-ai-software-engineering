import { HttpError } from "../utils/http";
import { parseCsv } from "./csvImporter";
import { parseJson } from "./jsonImporter";
import { parseXml } from "./xmlImporter";
import type { ImportResult } from "./types";

export type SupportedFormat = "csv" | "json" | "xml";

export function detectFormat(mimetype: string | undefined, filename: string | undefined): SupportedFormat {
  const mt = (mimetype ?? "").toLowerCase();
  const name = (filename ?? "").toLowerCase();
  if (mt.includes("csv") || name.endsWith(".csv")) return "csv";
  if (mt.includes("json") || name.endsWith(".json")) return "json";
  if (mt.includes("xml") || name.endsWith(".xml")) return "xml";
  throw new HttpError(400, "unsupported format", { mimetype, filename });
}

export function dispatch(buffer: Buffer, mimetype: string | undefined, filename: string | undefined): ImportResult {
  const fmt = detectFormat(mimetype, filename);
  switch (fmt) {
    case "csv":
      return parseCsv(buffer);
    case "json":
      return parseJson(buffer);
    case "xml":
      return parseXml(buffer);
  }
}

export { parseCsv, parseJson, parseXml };
export type { ImportResult } from "./types";
