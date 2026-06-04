# FinTech Specification Rules

## Scope
- This project defines a regulated virtual card lifecycle feature intended to guide production implementation.
- Treat `specification.md`, `agents.md`, and this rules file as source-of-truth inputs for product, engineering, security, compliance, and verification work.

## Specification Quality
- Keep requirements traceable from high-level objective to mid-level objective to low-level task.
- Reference objective IDs from `specification.md` when adding tasks, tests, or rationale.
- Include acceptance criteria for implementation-oriented tasks.
- Include beginning and ending context when describing agent work.

## FinTech Safety Defaults
- Never include full PAN, CVV, raw identity document values, or unnecessary PII in examples.
- Use masked card examples such as `**** **** **** 4242` only when a card display example is needed.
- Use synthetic users, synthetic tokens, and fake transactions in fixtures and examples.
- Prefer fail-closed behavior for authorization, audit logging, processor uncertainty, and compliance review.

## Language and Naming
- Use precise terms: `card_id`, `issuer_card_token`, `idempotency_key`, `audit_event`, `reason_code`, `minor_units`, and `currency`.
- Avoid vague wording such as "should be secure", "fast enough", "probably", or "best effort" unless a measurable target or review step follows.
- Use active voice and concise Markdown tables for traceability, verification, edge cases, and performance targets.

## Verification Rules
- Every mid-level objective needs at least one verification method.
- Edge cases must include expected user-visible behavior and audit/compliance behavior.
- Performance targets must be measurable and labeled as assumed targets when hypothetical.
- Security and compliance requirements must appear in the specification, not only in supporting docs.
