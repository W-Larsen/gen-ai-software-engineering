import type { Category, ClassificationResult, Priority } from "../models/ticket.schema";
import { CATEGORY_RULES, PRIORITY_RULES, findMatches } from "./rules";

export interface ClassifiableTicket {
  subject: string;
  description: string;
}

export function classify(ticket: ClassifiableTicket): ClassificationResult {
  const text = `${ticket.subject} ${ticket.description}`;

  let priority: Priority = "medium";
  let priorityKeywords: string[] = [];
  for (const rule of PRIORITY_RULES) {
    const matches = findMatches(text, rule.keywords);
    if (matches.length > 0) {
      priority = rule.priority;
      priorityKeywords = matches;
      break;
    }
  }

  let category: Category = "other";
  let bestCount = 0;
  let categoryKeywords: string[] = [];
  for (const rule of CATEGORY_RULES) {
    const matches = findMatches(text, rule.keywords);
    if (matches.length > bestCount) {
      bestCount = matches.length;
      category = rule.category;
      categoryKeywords = matches;
    }
  }

  const keywords_found = Array.from(new Set([...priorityKeywords, ...categoryKeywords]));
  const confidence = Math.min(1, 0.4 + 0.15 * keywords_found.length);

  let reasoning: string;
  if (keywords_found.length === 0) {
    reasoning = "No keywords matched; defaulted to other/medium.";
  } else {
    const catPart = categoryKeywords.length
      ? `category '${category}' chosen due to keywords [${categoryKeywords.join(", ")}]`
      : `category defaulted to '${category}'`;
    const priPart = priorityKeywords.length
      ? `priority '${priority}' due to [${priorityKeywords.join(", ")}]`
      : `priority defaulted to '${priority}'`;
    reasoning = `${catPart}; ${priPart}.`;
  }

  return { category, priority, confidence, reasoning, keywords_found };
}
