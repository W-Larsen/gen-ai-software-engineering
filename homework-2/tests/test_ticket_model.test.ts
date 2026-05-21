import { TicketCreateSchema, TicketUpdateSchema } from "../src/models/ticket.schema";
import { makeTicketInput } from "./helpers";

describe("Ticket model validation", () => {
  it("accepts a fully valid input", () => {
    const res = TicketCreateSchema.safeParse(makeTicketInput());
    expect(res.success).toBe(true);
  });

  it("rejects missing required customer_email", () => {
    const { customer_email, ...rest } = makeTicketInput();
    const res = TicketCreateSchema.safeParse(rest);
    expect(res.success).toBe(false);
  });

  it("rejects invalid email format", () => {
    const res = TicketCreateSchema.safeParse(makeTicketInput({ customer_email: "not-email" }));
    expect(res.success).toBe(false);
  });

  it("rejects subject shorter than 1 or longer than 200", () => {
    expect(TicketCreateSchema.safeParse(makeTicketInput({ subject: "" })).success).toBe(false);
    expect(TicketCreateSchema.safeParse(makeTicketInput({ subject: "x".repeat(201) })).success).toBe(false);
  });

  it("rejects description shorter than 10 or longer than 2000", () => {
    expect(TicketCreateSchema.safeParse(makeTicketInput({ description: "short" })).success).toBe(false);
    expect(TicketCreateSchema.safeParse(makeTicketInput({ description: "y".repeat(2001) })).success).toBe(false);
  });

  it("rejects invalid enum values", () => {
    const bad = { ...makeTicketInput(), category: "nope" as unknown as undefined };
    expect(TicketCreateSchema.safeParse(bad).success).toBe(false);
    const bad2 = { ...makeTicketInput(), priority: "extreme" as unknown as undefined };
    expect(TicketCreateSchema.safeParse(bad2).success).toBe(false);
    const bad3 = { ...makeTicketInput(), status: "weird" as unknown as undefined };
    expect(TicketCreateSchema.safeParse(bad3).success).toBe(false);
  });

  it("rejects non-string tags", () => {
    const bad = { ...makeTicketInput(), tags: [1, 2, 3] as unknown as string[] };
    expect(TicketCreateSchema.safeParse(bad).success).toBe(false);
  });

  it("rejects invalid metadata.source enum", () => {
    const bad = { ...makeTicketInput(), metadata: { source: "carrier_pigeon" as unknown as "email" } };
    expect(TicketCreateSchema.safeParse(bad).success).toBe(false);
  });

  it("TicketUpdateSchema accepts partial input", () => {
    const res = TicketUpdateSchema.safeParse({ status: "in_progress" });
    expect(res.success).toBe(true);
  });
});
