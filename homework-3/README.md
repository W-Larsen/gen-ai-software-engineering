# Virtual Card FinTech Specification Package

## Owner and Summary

Owner: `Valentyn Korniienko`

This package defines the specification baseline for a regulated virtual card lifecycle application. The feature scope covers end-user virtual card creation, freeze/unfreeze controls, spending limits, transaction visibility, and internal ops/compliance review.

Project documents:
- `specification.md`: layered product and engineering specification.
- `agents.md`: AI agent guidelines for future implementation work.
- `.cursor/rules/fintech-spec-rules.md`: editor/AI rules for consistent FinTech-sensitive work.
- `README.md`: rationale and best-practice mapping.

## Rationale

The specification uses virtual cards because the feature is focused enough for clear implementation planning but realistic enough to require meaningful FinTech controls. It naturally includes user-facing flows, internal review workflows, sensitive card data boundaries, state transitions, audit trails, idempotent writes, rate limits, and external issuer processor failure modes.

The structure follows the provided template but expands it with stronger traceability:
- The high-level objective defines the product outcome and scope boundary.
- Mid-level objectives are labeled `M1` through `M7` so tasks and verification can refer back to them.
- Non-functional requirements include security, privacy, reliability, consistency, and measurable performance targets.
- Low-level tasks are written as executable slices with acceptance criteria.
- Edge cases describe both user-visible behavior and audit/compliance implications.
- Verification maps each objective to concrete test or review categories.

The performance targets are labeled as assumed targets until they are validated against real traffic, infrastructure, and issuer processor behavior. The numbers are chosen to match common FinTech UX expectations: freeze/unfreeze actions should feel immediate, card creation may depend on an external issuer processor, transaction reads need bounded pagination, and compliance dashboards can tolerate short freshness delays for derived risk signals.

## Industry Best Practices Included

| Practice | Where it appears | Why it matters |
| --- | --- | --- |
| Sensitive card data minimization | `specification.md` Security and privacy; `agents.md` Domain Rules; `.cursor/rules/fintech-spec-rules.md` FinTech Safety Defaults | Prevents PAN/CVV exposure and reduces compliance risk. |
| Tokenized identifiers | `specification.md` Implementation Notes | Keeps processor card references separate from local application identity. |
| Idempotent writes | `specification.md` API and workflow semantics; Low-Level Tasks 2 and 3 | Prevents duplicate cards or duplicate state changes during retries. |
| Append-only audit events | `specification.md` Compliance and auditability; Low-Level Task 7 | Supports regulated investigations and operational accountability. |
| Role-based access control | `specification.md` Security and privacy; Low-Level Task 8 | Separates end-user, support, ops, compliance, and system permissions. |
| Exact money handling | `specification.md` Domain model guardrails; Low-Level Task 4 | Avoids rounding defects in spending limits. |
| Fail-closed behavior | `specification.md` Edge case policy; `agents.md` Edge Case Handling | Avoids unsafe success states when authorization, audit, or processor state is uncertain. |
| Explicit verification mapping | `specification.md` Verification Strategy | Makes the specification checkable by engineers, reviewers, and AI agents. |
| Measurable SLO-style targets | `specification.md` Expected performance | Replaces vague performance language with testable expectations. |

## How to Use This Package

Use `specification.md` as the source of truth for future implementation. Use `agents.md` to guide AI coding agents or reviewers. Use `.cursor/rules/fintech-spec-rules.md` to keep editor-assisted changes aligned with the same FinTech-sensitive defaults.
