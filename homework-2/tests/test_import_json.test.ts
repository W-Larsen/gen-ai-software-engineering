import fs from "fs";
import path from "path";
import { parseJson } from "../src/importers/jsonImporter";

const fix = (n: string) => fs.readFileSync(path.join(__dirname, "fixtures", n));

describe("JSON importer", () => {
  it("parses a top-level array", () => {
    const result = parseJson(fix("tickets_valid.json"));
    expect(result.total).toBe(2);
    expect(result.successful).toBe(2);
    expect(result.failed).toEqual([]);
  });

  it("parses a wrapped { tickets: [...] } shape", () => {
    const result = parseJson(fix("tickets_valid_wrapped.json"));
    expect(result.total).toBe(1);
    expect(result.successful).toBe(1);
  });

  it("partitions mixed valid + invalid records", () => {
    const result = parseJson(fix("tickets_invalid_fields.json"));
    expect(result.total).toBe(2);
    expect(result.successful).toBe(1);
    expect(result.failed).toHaveLength(1);
  });

  it("returns graceful error on invalid JSON syntax", () => {
    const result = parseJson(Buffer.from("{not valid"));
    expect(result.successful).toBe(0);
    expect(result.failed[0].errors[0]).toMatch(/malformed json/);
  });

  it("returns row-level error for non-object element", () => {
    const result = parseJson(Buffer.from(JSON.stringify(["scalar"])));
    expect(result.total).toBe(1);
    expect(result.successful).toBe(0);
    expect(result.failed[0].errors[0]).toMatch(/must be an object/);
  });

  it("returns top-level error when JSON is not array or wrapped", () => {
    const result = parseJson(Buffer.from(JSON.stringify({ wrong: "shape" })));
    expect(result.successful).toBe(0);
    expect(result.failed[0].errors[0]).toMatch(/array or/);
  });
});
