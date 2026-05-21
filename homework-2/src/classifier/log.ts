import type { ClassificationResult } from "../models/ticket.schema";

export interface ClassificationLogEntry {
  ticket_id: string;
  at: string;
  result: ClassificationResult;
  manual_override?: boolean;
}

const entries: ClassificationLogEntry[] = [];

export function logDecision(entry: Omit<ClassificationLogEntry, "at">): void {
  entries.push({ ...entry, at: new Date().toISOString() });
}

export function getClassificationLog(): ClassificationLogEntry[] {
  return [...entries];
}

export function clearLog(): void {
  entries.length = 0;
}
