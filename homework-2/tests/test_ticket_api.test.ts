import request from "supertest";
import { createApp } from "../src/app";
import * as store from "../src/store/ticketStore";
import { clearLog } from "../src/classifier/log";
import { makeTicketInput } from "./helpers";

const app = createApp();

beforeEach(() => {
  store.clear();
  clearLog();
});

describe("Ticket API", () => {
  it("POST /tickets creates a ticket and returns 201 with UUID + timestamps", async () => {
    const res = await request(app).post("/tickets").send(makeTicketInput());
    expect(res.status).toBe(201);
    expect(res.body.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(res.body.created_at).toBeTruthy();
    expect(res.body.updated_at).toBeTruthy();
    expect(res.body.status).toBe("new");
    expect(res.body.priority).toBe("medium");
    expect(res.body.category).toBe("other");
  });

  it("POST /tickets returns 400 when a required field is missing", async () => {
    const { customer_email, ...rest } = makeTicketInput();
    const res = await request(app).post("/tickets").send(rest);
    expect(res.status).toBe(400);
    expect(res.body.error).toBe("validation_error");
  });

  it("POST /tickets returns 400 for invalid email", async () => {
    const res = await request(app).post("/tickets").send(makeTicketInput({ customer_email: "not-an-email" }));
    expect(res.status).toBe(400);
  });

  it("POST /tickets returns 400 for subject > 200 chars", async () => {
    const res = await request(app)
      .post("/tickets")
      .send(makeTicketInput({ subject: "x".repeat(201) }));
    expect(res.status).toBe(400);
  });

  it("GET /tickets returns empty initially", async () => {
    const res = await request(app).get("/tickets");
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(0);
    expect(res.body.tickets).toEqual([]);
  });

  it("GET /tickets filters by category", async () => {
    await request(app).post("/tickets").send(makeTicketInput({ category: "billing_question" }));
    await request(app).post("/tickets").send(makeTicketInput({ category: "bug_report" }));
    const res = await request(app).get("/tickets?category=billing_question");
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(1);
    expect(res.body.tickets[0].category).toBe("billing_question");
  });

  it("GET /tickets filters by priority and status combined", async () => {
    await request(app).post("/tickets").send(makeTicketInput({ priority: "high", status: "in_progress" }));
    await request(app).post("/tickets").send(makeTicketInput({ priority: "high", status: "new" }));
    await request(app).post("/tickets").send(makeTicketInput({ priority: "low", status: "in_progress" }));
    const res = await request(app).get("/tickets?priority=high&status=in_progress");
    expect(res.body.count).toBe(1);
  });

  it("GET /tickets/:id returns ticket then 404 for unknown id", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    const ok = await request(app).get(`/tickets/${created.body.id}`);
    expect(ok.status).toBe(200);
    expect(ok.body.id).toBe(created.body.id);
    const missing = await request(app).get("/tickets/00000000-0000-0000-0000-000000000000");
    expect(missing.status).toBe(404);
  });

  it("PUT /tickets/:id updates fields and bumps updated_at", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    await new Promise((r) => setTimeout(r, 5));
    const res = await request(app).put(`/tickets/${created.body.id}`).send({ status: "in_progress" });
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("in_progress");
    expect(new Date(res.body.updated_at).getTime()).toBeGreaterThan(new Date(created.body.updated_at).getTime());
  });

  it("PUT setting status=resolved sets resolved_at", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    const res = await request(app).put(`/tickets/${created.body.id}`).send({ status: "resolved" });
    expect(res.body.status).toBe("resolved");
    expect(res.body.resolved_at).toBeTruthy();
  });

  it("DELETE /tickets/:id returns 204 and subsequent GET is 404", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    const del = await request(app).delete(`/tickets/${created.body.id}`);
    expect(del.status).toBe(204);
    const after = await request(app).get(`/tickets/${created.body.id}`);
    expect(after.status).toBe(404);
  });

  it("PUT /tickets/:id returns 404 for unknown id", async () => {
    const res = await request(app)
      .put("/tickets/00000000-0000-0000-0000-000000000000")
      .send({ status: "in_progress" });
    expect(res.status).toBe(404);
  });
});
