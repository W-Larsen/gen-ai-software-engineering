import { v4 as uuidv4 } from "uuid";
import type {
  Category,
  Priority,
  Status,
  Ticket,
  TicketCreateInput,
  TicketUpdateInput
} from "../models/ticket.schema";

export interface ListFilters {
  category?: Category;
  priority?: Priority;
  status?: Status;
  assigned_to?: string;
  customer_id?: string;
}

const tickets = new Map<string, Ticket>();

const nowIso = (): string => new Date().toISOString();

export function create(input: TicketCreateInput): Ticket {
  const now = nowIso();
  const ticket: Ticket = {
    id: uuidv4(),
    customer_id: input.customer_id,
    customer_email: input.customer_email,
    customer_name: input.customer_name,
    subject: input.subject,
    description: input.description,
    category: input.category ?? "other",
    priority: input.priority ?? "medium",
    status: input.status ?? "new",
    created_at: now,
    updated_at: now,
    resolved_at: null,
    assigned_to: input.assigned_to ?? null,
    tags: input.tags ?? [],
    metadata: input.metadata
  };
  tickets.set(ticket.id, ticket);
  return ticket;
}

export function getById(id: string): Ticket | undefined {
  return tickets.get(id);
}

export function update(id: string, patch: TicketUpdateInput): Ticket | undefined {
  const current = tickets.get(id);
  if (!current) return undefined;
  const next: Ticket = { ...current };
  if (patch.customer_id !== undefined) next.customer_id = patch.customer_id;
  if (patch.customer_email !== undefined) next.customer_email = patch.customer_email;
  if (patch.customer_name !== undefined) next.customer_name = patch.customer_name;
  if (patch.subject !== undefined) next.subject = patch.subject;
  if (patch.description !== undefined) next.description = patch.description;
  if (patch.category !== undefined) next.category = patch.category;
  if (patch.priority !== undefined) next.priority = patch.priority;
  if (patch.status !== undefined) next.status = patch.status;
  if (patch.assigned_to !== undefined) next.assigned_to = patch.assigned_to;
  if (patch.tags !== undefined) next.tags = patch.tags;
  if (patch.metadata !== undefined) next.metadata = patch.metadata;
  if (patch.resolved_at !== undefined) next.resolved_at = patch.resolved_at ?? null;

  if (patch.status === "resolved" && !next.resolved_at) {
    next.resolved_at = nowIso();
  }
  next.updated_at = nowIso();
  tickets.set(id, next);
  return next;
}

export function replaceClassification(id: string, payload: {
  category: Category;
  priority: Priority;
  classification: Ticket["classification"];
}): Ticket | undefined {
  const current = tickets.get(id);
  if (!current) return undefined;
  const next: Ticket = {
    ...current,
    category: payload.category,
    priority: payload.priority,
    classification: payload.classification,
    updated_at: nowIso()
  };
  tickets.set(id, next);
  return next;
}

export function remove(id: string): boolean {
  return tickets.delete(id);
}

export function list(filters: ListFilters = {}): Ticket[] {
  const all = Array.from(tickets.values());
  return all.filter((t) => {
    if (filters.category && t.category !== filters.category) return false;
    if (filters.priority && t.priority !== filters.priority) return false;
    if (filters.status && t.status !== filters.status) return false;
    if (filters.assigned_to && t.assigned_to !== filters.assigned_to) return false;
    if (filters.customer_id && t.customer_id !== filters.customer_id) return false;
    return true;
  });
}

export function clear(): void {
  tickets.clear();
}

export function size(): number {
  return tickets.size;
}
