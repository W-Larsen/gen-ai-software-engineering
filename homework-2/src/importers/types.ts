import type { TicketCreateInput } from "../models/ticket.schema";

export interface ImportFailure {
  row: number;
  errors: string[];
}

export interface ImportResult {
  total: number;
  successful: number;
  failed: ImportFailure[];
  records: TicketCreateInput[];
}
