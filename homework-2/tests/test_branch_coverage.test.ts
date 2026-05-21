import path from "path";
import request from "supertest";
import { createApp } from "../src/app";
import * as store from "../src/store/ticketStore";
import { clearLog } from "../src/classifier/log";
import { dispatch } from "../src/importers";
import { makeTicketInput } from "./helpers";

const app = createApp();
const fixturePath = (n: string) => path.join(__dirname, "fixtures", n);

beforeEach(() => {
  store.clear();
  clearLog();
});

describe("Additional branch coverage", () => {
  it("PUT exercises every patchable field", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    const id = created.body.id;
    const patch = {
      customer_id: "C-NEW",
      customer_email: "new@example.com",
      customer_name: "New Name",
      subject: "New subject",
      description: "New description that is long enough to pass.",
      category: "bug_report",
      priority: "high",
      status: "in_progress",
      assigned_to: "agent-1",
      tags: ["one", "two"],
      metadata: { source: "chat" }
    };
    const res = await request(app).put(`/tickets/${id}`).send(patch);
    expect(res.status).toBe(200);
    expect(res.body.customer_id).toBe("C-NEW");
    expect(res.body.assigned_to).toBe("agent-1");
    expect(res.body.tags).toEqual(["one", "two"]);
    expect(res.body.metadata.source).toBe("chat");
  });

  it("PUT can clear resolved_at by sending null", async () => {
    const created = await request(app).post("/tickets").send(makeTicketInput());
    await request(app).put(`/tickets/${created.body.id}`).send({ status: "resolved" });
    const cleared = await request(app).put(`/tickets/${created.body.id}`).send({ resolved_at: null });
    expect(cleared.body.resolved_at).toBeNull();
  });

  it("POST /tickets/import returns 400 when no file is attached", async () => {
    const res = await request(app).post("/tickets/import");
    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/file is required/);
  });

  it("dispatch throws HttpError 400 for unsupported format", () => {
    expect(() => dispatch(Buffer.from("hi"), "application/octet-stream", "file.bin")).toThrow(/unsupported format/);
  });

  it("POST /tickets/import returns 400 for unsupported format", async () => {
    const res = await request(app)
      .post("/tickets/import")
      .attach("file", Buffer.from("noop"), { filename: "data.bin", contentType: "application/octet-stream" });
    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/unsupported format/);
  });

  it("DELETE returns 404 for unknown id", async () => {
    const res = await request(app).delete("/tickets/00000000-0000-0000-0000-000000000000");
    expect(res.status).toBe(404);
  });

  it("auto-classify returns 404 for unknown id", async () => {
    const res = await request(app).post("/tickets/00000000-0000-0000-0000-000000000000/auto-classify");
    expect(res.status).toBe(404);
  });

  it("POST /tickets with autoClassify in JSON body triggers classification", async () => {
    const res = await request(app)
      .post("/tickets")
      .send({ ...makeTicketInput({ subject: "Production down", description: "Production down outage now happening everywhere." }), autoClassify: true });
    expect(res.status).toBe(201);
    expect(res.body.classification.priority).toBe("urgent");
  });

  it("invalid filter enum on GET returns 400", async () => {
    const res = await request(app).get("/tickets?category=not_real");
    expect(res.status).toBe(400);
  });

  it("filters by assigned_to and customer_id", async () => {
    await request(app).post("/tickets").send(makeTicketInput({ customer_id: "C-A", assigned_to: "agent-x" }));
    await request(app).post("/tickets").send(makeTicketInput({ customer_id: "C-B", assigned_to: "agent-y" }));
    const a = await request(app).get("/tickets?assigned_to=agent-x");
    expect(a.body.count).toBe(1);
    const b = await request(app).get("/tickets?customer_id=C-B");
    expect(b.body.count).toBe(1);
  });

  it("CSV importer reads source from non-prefixed columns when present", async () => {
    const csv = [
      "customer_id,customer_email,customer_name,subject,description,source,browser,device_type",
      "C-X,user@example.com,User,Subject text,This description is long enough certainly,web_form,Chrome,mobile"
    ].join("\n");
    const res = await request(app)
      .post("/tickets/import")
      .attach("file", Buffer.from(csv), { filename: "alt.csv", contentType: "text/csv" });
    expect(res.status).toBe(200);
    expect(res.body.successful).toBe(1);
    expect(res.body.tickets[0].metadata).toEqual({ source: "web_form", browser: "Chrome", device_type: "mobile" });
  });

  it("XML missing <tickets><ticket> reports a top-level error", async () => {
    const xml = `<?xml version="1.0"?><other></other>`;
    const res = await request(app)
      .post("/tickets/import")
      .attach("file", Buffer.from(xml), { filename: "bad.xml", contentType: "application/xml" });
    expect(res.body.successful).toBe(0);
    expect(res.body.failed[0].errors[0]).toMatch(/<tickets><ticket>/);
  });

  it("XML rejects non-object ticket element (scalar)", async () => {
    const xml = `<?xml version="1.0"?><tickets><ticket>just text</ticket></tickets>`;
    const res = await request(app)
      .post("/tickets/import")
      .attach("file", Buffer.from(xml), { filename: "scalar.xml", contentType: "application/xml" });
    expect(res.body.successful).toBe(0);
    expect(res.body.failed).toHaveLength(1);
  });

  it("error handler returns 500 for unexpected errors and 400 for multer errors", async () => {
    const express = require("express");
    const multer = require("multer");
    const { errorHandler } = require("../src/middleware/errorHandler");

    const boomApp = express();
    boomApp.get("/boom", (_req: unknown, _res: unknown, next: (e: unknown) => void) => next(new Error("kaboom")));
    boomApp.get("/multer", (_req: unknown, _res: unknown, next: (e: unknown) => void) =>
      next(new multer.MulterError("LIMIT_FILE_SIZE", "file"))
    );
    boomApp.get("/string", (_req: unknown, _res: unknown, next: (e: unknown) => void) => next("just a string"));
    boomApp.use(errorHandler);

    const r1 = await request(boomApp).get("/boom");
    expect(r1.status).toBe(500);
    expect(r1.body.error).toBe("internal_error");

    const r2 = await request(boomApp).get("/multer");
    expect(r2.status).toBe(400);
    expect(r2.body.error).toBe("upload_error");

    const r3 = await request(boomApp).get("/string");
    expect(r3.status).toBe(500);
  });
});
