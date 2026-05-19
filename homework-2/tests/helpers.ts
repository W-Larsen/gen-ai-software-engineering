import type { TicketCreateInput } from "../src/models/ticket.schema";

export function makeTicketInput(overrides: Partial<TicketCreateInput> = {}): TicketCreateInput {
  return {
    customer_id: "C-1",
    customer_email: "alice@example.com",
    customer_name: "Alice",
    subject: "Subject line",
    description: "This is a description that is long enough to validate.",
    metadata: { source: "web_form" },
    ...overrides
  };
}
