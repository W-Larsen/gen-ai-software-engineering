import { classify } from "../src/classifier/classifier";

describe("Auto-classification", () => {
  it('marks "can\'t access" subject as urgent', () => {
    const r = classify({ subject: "I can't access my dashboard", description: "Need help logging in right now please." });
    expect(r.priority).toBe("urgent");
    expect(r.keywords_found).toEqual(expect.arrayContaining(["can't access"]));
  });

  it('marks "production down" as urgent', () => {
    const r = classify({ subject: "Production down", description: "Our production environment is completely down for users." });
    expect(r.priority).toBe("urgent");
  });

  it('marks "security" mention as urgent', () => {
    const r = classify({ subject: "Possible security issue", description: "We may have a security incident on customer accounts." });
    expect(r.priority).toBe("urgent");
  });

  it('marks "blocking" / "asap" as high', () => {
    const r = classify({ subject: "blocking deploy", description: "This is blocking our team and needed asap please." });
    expect(r.priority).toBe("high");
  });

  it('marks "minor" / "cosmetic" as low', () => {
    const r = classify({ subject: "minor cosmetic issue", description: "Just a minor cosmetic alignment problem on the page." });
    expect(r.priority).toBe("low");
  });

  it("defaults to medium priority when no keywords match", () => {
    const r = classify({ subject: "Hello", description: "Random message with no relevant keywords whatsoever today." });
    expect(r.priority).toBe("medium");
    expect(r.category).toBe("other");
    expect(r.confidence).toBe(0.4);
    expect(r.reasoning).toMatch(/No keywords matched/);
  });

  it('classifies "password reset" as account_access', () => {
    const r = classify({ subject: "Password reset", description: "I need to reset password for my login on the portal." });
    expect(r.category).toBe("account_access");
  });

  it('classifies "refund invoice" as billing_question', () => {
    const r = classify({ subject: "Refund my invoice", description: "Please process a refund for the recent invoice charge." });
    expect(r.category).toBe("billing_question");
  });

  it('classifies "steps to reproduce" as bug_report', () => {
    const r = classify({
      subject: "Defect report",
      description: "Here are the steps to reproduce the defect consistently every time."
    });
    expect(r.category).toBe("bug_report");
  });

  it("confidence rises with more keywords and reasoning mentions them", () => {
    const r = classify({
      subject: "Critical: production down with security concern",
      description: "Login broken, password reset failing, billing also showing wrong invoice."
    });
    expect(r.confidence).toBeGreaterThan(0.7);
    expect(r.reasoning).toContain("priority");
    expect(r.keywords_found.length).toBeGreaterThanOrEqual(3);
  });
});
