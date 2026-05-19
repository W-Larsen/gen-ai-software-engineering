import { performance } from "perf_hooks";
import request from "supertest";
import { createApp } from "../src/app";
import * as store from "../src/store/ticketStore";
import { classify } from "../src/classifier/classifier";
import { parseCsv } from "../src/importers/csvImporter";
import { makeTicketInput } from "./helpers";

const app = createApp();

beforeEach(() => store.clear());

describe("Performance benchmarks", () => {
  it("creates 1000 tickets in <1500ms", async () => {
    const t = performance.now();
    for (let i = 0; i < 1000; i++) {
      store.create(makeTicketInput({ customer_id: `C-${i}` }));
    }
    expect(performance.now() - t).toBeLessThan(1500);
    expect(store.size()).toBe(1000);
  });

  it("lists 1000 tickets with filter in <200ms", () => {
    for (let i = 0; i < 1000; i++) {
      store.create(makeTicketInput({
        customer_id: `C-${i}`,
        priority: i % 2 === 0 ? "high" : "low"
      }));
    }
    const t = performance.now();
    const r = store.list({ priority: "high" });
    expect(performance.now() - t).toBeLessThan(200);
    expect(r.length).toBe(500);
  });

  it("parses a 500-row CSV in <2000ms", () => {
    const header = "customer_id,customer_email,customer_name,subject,description,metadata.source\n";
    let body = "";
    for (let i = 0; i < 500; i++) {
      body += `C-${i},user${i}@example.com,User${i},Subject ${i},Description that is long enough number ${i}.,web_form\n`;
    }
    const t = performance.now();
    const result = parseCsv(Buffer.from(header + body));
    expect(performance.now() - t).toBeLessThan(2000);
    expect(result.successful).toBe(500);
  });

  it("classifies 1000 tickets in <1000ms", () => {
    const sample = {
      subject: "Production down — can't access account, security risk",
      description: "Critical billing invoice issue, please refund asap, blocking team."
    };
    const t = performance.now();
    for (let i = 0; i < 1000; i++) classify(sample);
    expect(performance.now() - t).toBeLessThan(1000);
  });

  it("handles 50 concurrent GET /tickets requests in <1500ms", async () => {
    for (let i = 0; i < 25; i++) store.create(makeTicketInput({ customer_id: `C-${i}` }));
    const t = performance.now();
    await Promise.all(Array.from({ length: 50 }, () => request(app).get("/tickets")));
    expect(performance.now() - t).toBeLessThan(1500);
  });
});
