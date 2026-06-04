# Agent Guidelines for Virtual Card FinTech Work

These rules guide AI agents working from the virtual card lifecycle specification. They apply to future implementation, review, testing, and documentation work in this project.

## Project Assumptions
- Treat this as a regulated FinTech application with consumer cardholder workflows and internal ops/compliance workflows.
- Prefer conservative, auditable behavior over convenience when security, privacy, or compliance is involved.
- Do not invent production integrations, processor APIs, or legal requirements beyond the specification without documenting assumptions.
- Keep work traceable to `specification.md` objectives and low-level tasks.

## Domain Rules
- Never store, log, display, or generate full PAN or CVV.
- Use tokenized card references and local opaque IDs for card identity.
- Represent money using integer minor units plus ISO 4217 currency, or an exact decimal type if the chosen language requires it.
- Treat card state transitions as a controlled state machine.
- Do not let users clear an ops/compliance freeze.
- Keep support notes and compliance investigation notes separate.

## Security and Compliance Defaults
- Deny access by default when ownership, role, or policy context is unclear.
- Use role-based access control for end user, support, compliance analyst, ops manager, and system actor.
- Require audit events for every sensitive read or write listed in `specification.md`.
- Persist audit events before returning success for sensitive write actions.
- Redact sensitive data in logs, traces, analytics events, screenshots, and test fixtures.
- Prefer explicit reason codes over free-text fields for compliance and operations actions.

## Testing and Verification Expectations
- Map tests and review checks back to mid-level objective IDs from `specification.md`.
- Include positive, negative, edge-case, authorization, audit, and failure-injection scenarios.
- Verify idempotency for create, freeze, unfreeze, and limit update commands.
- Verify that duplicate and conflicting requests produce deterministic outcomes.
- Include log and fixture scanning for prohibited card data.
- Include performance checks for documented assumed p95 latency, pagination, and rate-limit targets when implementation exists.

## Edge Case Handling
- Treat issuer processor uncertainty as pending or unavailable; do not report success without confirmation.
- Treat audit persistence failure as a blocker for sensitive write success.
- Serialize concurrent state changes and return the final accepted state.
- Record denied access attempts as audit or risk events.
- Use neutral user-facing messages for suspected fraud or compliance investigations.

## Documentation and Style
- Keep Markdown headings clear and traceable.
- Use objective IDs such as `M1` and task numbers when referencing requirements.
- Avoid vague phrases like "secure enough", "fast", or "handle errors"; use measurable or reviewable criteria.
- Document assumptions whenever a requirement depends on a hypothetical system, external provider, or policy choice.
- Keep future implementation work aligned with `specification.md`, `agents.md`, and `.cursor/rules/fintech-spec-rules.md`.
