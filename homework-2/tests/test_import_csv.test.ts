import fs from "fs";
import path from "path";
import { parseCsv } from "../src/importers/csvImporter";

const fix = (n: string) => fs.readFileSync(path.join(__dirname, "fixtures", n));

describe("CSV importer", () => {
  it("parses a fully valid CSV file", () => {
    const result = parseCsv(fix("tickets_valid.csv"));
    expect(result.total).toBe(3);
    expect(result.successful).toBe(3);
    expect(result.failed).toEqual([]);
    expect(result.records[0].customer_id).toBe("C-100");
  });

  it("splits the tags column on commas", () => {
    const result = parseCsv(fix("tickets_valid.csv"));
    expect(result.records[0].tags).toEqual(["login", "urgent"]);
  });

  it("maps metadata columns into nested object", () => {
    const result = parseCsv(fix("tickets_valid.csv"));
    expect(result.records[0].metadata).toEqual({
      source: "web_form",
      browser: "Chrome",
      device_type: "desktop"
    });
  });

  it("partitions rows with invalid email into failed[] while keeping valid rows", () => {
    const result = parseCsv(fix("tickets_invalid_row.csv"));
    expect(result.total).toBe(2);
    expect(result.successful).toBe(1);
    expect(result.failed).toHaveLength(1);
    expect(result.failed[0].errors.join(" ")).toMatch(/customer_email/);
  });

  it("handles malformed CSV gracefully", () => {
    const result = parseCsv(fix("tickets_malformed.csv"));
    expect(result.successful).toBe(0);
    expect(result.failed).toHaveLength(1);
    expect(result.failed[0].errors[0]).toMatch(/malformed csv/);
  });

  it("returns total 0 on empty file", () => {
    const result = parseCsv(Buffer.from(""));
    expect(result.total).toBe(0);
    expect(result.successful).toBe(0);
  });
});
