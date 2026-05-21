import fs from "fs";
import path from "path";
import { parseXml } from "../src/importers/xmlImporter";

const fix = (n: string) => fs.readFileSync(path.join(__dirname, "fixtures", n));

describe("XML importer", () => {
  it("parses standard <tickets><ticket>...", () => {
    const result = parseXml(fix("tickets_valid.xml"));
    expect(result.total).toBe(2);
    expect(result.successful).toBe(2);
    expect(result.failed).toEqual([]);
  });

  it("normalizes a single <ticket> element to an array", () => {
    const result = parseXml(fix("tickets_xml_single.xml"));
    expect(result.total).toBe(1);
    expect(result.successful).toBe(1);
  });

  it("collects multiple <tag> children into a tags array", () => {
    const result = parseXml(fix("tickets_valid.xml"));
    expect(result.records[0].tags).toEqual(["security", "urgent"]);
  });

  it("returns graceful error on malformed XML", () => {
    const result = parseXml(fix("tickets_malformed.xml"));
    expect(result.successful).toBe(0);
    expect(result.failed[0].errors[0]).toMatch(/malformed xml/);
  });

  it("reports missing required field as row failure", () => {
    const bad = Buffer.from(`<?xml version="1.0"?><tickets><ticket><customer_id>X</customer_id><metadata><source>web_form</source></metadata></ticket></tickets>`);
    const result = parseXml(bad);
    expect(result.total).toBe(1);
    expect(result.successful).toBe(0);
    expect(result.failed).toHaveLength(1);
  });
});
