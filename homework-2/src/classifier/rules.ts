import type { Category, Priority } from "../models/ticket.schema";

export interface PriorityRule {
  priority: Priority;
  keywords: string[];
}

export interface CategoryRule {
  category: Category;
  keywords: string[];
}

export const PRIORITY_RULES: PriorityRule[] = [
  {
    priority: "urgent",
    keywords: ["can't access", "cannot access", "critical", "production down", "security"]
  },
  {
    priority: "high",
    keywords: ["important", "blocking", "asap"]
  },
  {
    priority: "low",
    keywords: ["minor", "cosmetic", "suggestion"]
  }
];

export const CATEGORY_RULES: CategoryRule[] = [
  {
    category: "account_access",
    keywords: ["login", "log in", "password", "2fa", "mfa", "locked out", "sign in", "reset password"]
  },
  {
    category: "technical_issue",
    keywords: ["error", "crash", "freeze", "broken", "exception", "stack trace", "500", "timeout"]
  },
  {
    category: "billing_question",
    keywords: ["invoice", "payment", "refund", "charge", "subscription", "billing", "receipt"]
  },
  {
    category: "feature_request",
    keywords: ["feature request", "please add", "would love", "enhancement"]
  },
  {
    category: "bug_report",
    keywords: ["bug", "defect", "reproduce", "steps to reproduce", "regression"]
  }
];

const ESCAPE_RE = /[.*+?^${}()|[\]\\]/g;

export function buildKeywordRegex(keyword: string): RegExp {
  const escaped = keyword.replace(ESCAPE_RE, "\\$&");
  // Word boundaries are unreliable around apostrophes/spaces; require the keyword
  // to start at a word/string boundary and not be glued to a letter on either side.
  return new RegExp(`(^|[^a-z0-9])${escaped}(?![a-z0-9])`, "i");
}

export function findMatches(text: string, keywords: string[]): string[] {
  return keywords.filter((kw) => buildKeywordRegex(kw).test(text));
}
