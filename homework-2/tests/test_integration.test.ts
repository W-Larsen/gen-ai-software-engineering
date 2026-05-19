import fs from "fs";
import path from "path";
import request from "supertest";
import { createApp } from "../src/app";
import * as store from "../src/store/ticketStore";
import { clearLog, getClassificationLog } from "../src/classifier/log";
import { makeTicketInput } from "./helpers";

const app = createApp();
const fixturePath = (n: string) => path.join(__dirname, "fixtures", n);

beforeEach(() => {
  store.clear();
  clearLog();
});

describe("Integration", () => {
  it("complete ticket lifecycle: create → list → get → update → delete", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    expect(created.status).toBe(201);
    const id = created.body.id;
    const list1 = await request(app).get("/tickets");
    expect(list1.body.count).toBe(1);
    const get = await request(app).get(`/tickets/${id}`);
    expect(get.status).toBe(200);
    const upd = await request(app).put(`/tickets/${id}`).send({ status: "resolved" });
    expect(upd.body.resolved_at).toBeTruthy();
    const del = await request(app).delete(`/tickets/${id}`);
    expect(del.status).toBe(204);
    const list2 = await request(app).get("/tickets");
    expect(list2.body.count).toBe(0);
  });

  it("bulk-imports CSV and lists filtered results", async () => {
    const imp = await request(app)
      .post("/tickets/import")
      .attach("file", fixturePath("tickets_valid.csv"));
    expect(imp.status).toBe(200);
    expect(imp.body.successful).toBe(3);
    const filtered = await request(app).get("/tickets?category=billing_question");
    expect(filtered.body.count).toBe(1);
  });

  it("bulk import with autoClassify=true classifies records", async () => {
    const imp = await request(app)
      .post("/tickets/import?autoClassify=true")
      .attach("file", fixturePath("tickets_valid.json"));
    expect(imp.status).toBe(200);
    expect(imp.body.successful).toBe(2);
    // First JSON ticket: "Production down" → urgent; second: "feature request" → feature_request
    const tickets = imp.body.tickets;
    expect(tickets[0].priority).toBe("urgent");
    expect(tickets[0].classification.keywords_found).toEqual(expect.arrayContaining(["production down"]));
    expect(tickets[1].category).toBe("feature_request");
    expect(getClassificationLog().length).toBeGreaterThanOrEqual(2);
  });

  it("manual category survives autoClassify on create", async () => {
    const res = await request(app)
      .post("/tickets?autoClassify=true")
      .send(makeTicketInput({
        category: "other",
        priority: "low",
        subject: "Production down",
        description: "Production down, security incident, urgent please help."
      }));
    expect(res.status).toBe(201);
    expect(res.body.category).toBe("other");
    expect(res.body.priority).toBe("low");
    expect(res.body.classification.priority).toBe("urgent");
    const log = getClassificationLog();
    expect(log[0].manual_override).toBe(true);
  });

  it("POST /tickets/:id/auto-classify overwrites category and stores confidence", async () => {
    const created = await request(app).post("/tickets").send(
      makeTicketInput({ subject: "Cannot access account", description: "I cannot access my password reset link." })
    );
    expect(created.body.category).toBe("other");
    const res = await request(app).post(`/tickets/${created.body.id}/auto-classify`);
    expect(res.status).toBe(200);
    expect(res.body.classification.priority).toBe("urgent");
    expect(res.body.ticket.priority).toBe("urgent");
    expect(res.body.ticket.classification.confidence).toBeGreaterThan(0.4);
  });
});
