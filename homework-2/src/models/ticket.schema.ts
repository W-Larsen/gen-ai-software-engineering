import { z } from "zod";

export const CategoryEnum = z.enum([
  "account_access",
  "technical_issue",
  "billing_question",
  "feature_request",
  "bug_report",
  "other"
]);

export const PriorityEnum = z.enum(["urgent", "high", "medium", "low"]);

export const StatusEnum = z.enum([
  "new",
  "in_progress",
  "waiting_customer",
  "resolved",
  "closed"
]);

export const SourceEnum = z.enum(["web_form", "email", "api", "chat", "phone"]);
export const DeviceEnum = z.enum(["desktop", "mobile", "tablet"]);

export const MetadataSchema = z.object({
  source: SourceEnum,
  browser: z.string().optional(),
  device_type: DeviceEnum.optional()
});

export const ClassificationResultSchema = z.object({
  category: CategoryEnum,
  priority: PriorityEnum,
  confidence: z.number().min(0).max(1),
  reasoning: z.string(),
  keywords_found: z.array(z.string())
});

export const TicketCreateSchema = z.object({
  customer_id: z.string().min(1),
  customer_email: z.string().email(),
  customer_name: z.string().min(1),
  subject: z.string().min(1).max(200),
  description: z.string().min(10).max(2000),
  category: CategoryEnum.optional(),
  priority: PriorityEnum.optional(),
  status: StatusEnum.optional(),
  assigned_to: z.string().nullable().optional(),
  tags: z.array(z.string()).optional(),
  metadata: MetadataSchema
});

export const TicketUpdateSchema = TicketCreateSchema.partial().extend({
  resolved_at: z.string().datetime().nullable().optional()
});

export type Category = z.infer<typeof CategoryEnum>;
export type Priority = z.infer<typeof PriorityEnum>;
export type Status = z.infer<typeof StatusEnum>;
export type Source = z.infer<typeof SourceEnum>;
export type Device = z.infer<typeof DeviceEnum>;
export type Metadata = z.infer<typeof MetadataSchema>;
export type TicketCreateInput = z.infer<typeof TicketCreateSchema>;
export type TicketUpdateInput = z.infer<typeof TicketUpdateSchema>;
export type ClassificationResult = z.infer<typeof ClassificationResultSchema>;

export interface Ticket {
  id: string;
  customer_id: string;
  customer_email: string;
  customer_name: string;
  subject: string;
  description: string;
  category: Category;
  priority: Priority;
  status: Status;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  assigned_to: string | null;
  tags: string[];
  metadata: Metadata;
  classification?: ClassificationResult;
}
