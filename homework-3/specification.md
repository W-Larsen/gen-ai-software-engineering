# Virtual Card Lifecycle Specification

> Ingest the information from this file to understand the expected product, engineering, security, compliance, and verification behavior for a regulated FinTech feature.

## High-Level Objective
- Build a secure self-service virtual card management experience that lets eligible end users create cards, freeze or unfreeze them, set spending limits, and view transactions while giving internal operations and compliance teams auditable oversight without exposing sensitive card data.

Scope boundary: this specification covers virtual card lifecycle behavior and supporting internal review workflows, not card network settlement, issuer processor internals, or general banking ledger design.

## Mid-Level Objectives

| ID | Objective | Observable outcome |
| --- | --- | --- |
| M1 | End users can create eligible virtual cards safely. | A verified user can create one or more virtual cards within policy limits; duplicate requests do not create duplicate cards. |
| M2 | End users can freeze and unfreeze cards with clear state transitions. | A card can move between `active`, `frozen_by_user`, `frozen_by_ops`, and `closed` states according to role and policy rules. |
| M3 | End users can set and review spending limits. | Per-card daily and monthly limits are stored, displayed in minor currency units, and validated against product policy. |
| M4 | End users can view recent card transactions. | Transactions are paginated, masked, sortable by posted time, and include empty, pending, declined, and reversed states. |
| M5 | Internal ops and compliance users can review sensitive activity. | Authorized staff can search card records by non-sensitive identifiers, inspect audit history, and flag suspicious patterns. |
| M6 | Sensitive actions are auditable, secure, and privacy-preserving. | Card lifecycle, limit, permission, and review actions create immutable audit events without full PAN, CVV, or unnecessary PII. |
| M7 | Failure modes are explicit and user-safe. | Partial failures, stale data, permission violations, and external issuer errors return clear statuses and preserve audit evidence. |

## Non-Functional and Policy Requirements

### Security and privacy
- Full PAN and CVV must never be stored in this application database, logs, analytics events, screenshots, test fixtures, or support tooling.
- Card references must use tokenized identifiers from the issuer processor plus a local opaque `card_id`.
- Displayed card data must show only brand, last four digits, expiry month/year where allowed, and masked cardholder name when required by policy.
- Role-based access control must distinguish end user, support, compliance analyst, ops manager, and system actor.
- Privileged internal actions must require step-up authentication or an equivalent strong session assurance check.

### Compliance and auditability
- Every create, freeze, unfreeze, limit change, transaction visibility action, and internal review action must emit an audit event.
- Audit events must include actor type, actor ID, subject user ID, card ID, timestamp, request ID, idempotency key where present, source channel, action, outcome, and policy decision.
- Audit events must be append-only and must not be deleted by normal user or support actions.
- Compliance review notes must be separated from user-visible support notes and must not expose regulated investigation details to end users.

### Reliability and consistency
- Assumed API availability target: 99.9% monthly for card lifecycle and transaction read operations.
- Card state writes must be idempotent and safe to retry with the same idempotency key for at least 24 hours.
- After successful card state or limit updates, the end-user view should reflect the new state within 2 seconds under normal operating conditions.
- If issuer processor confirmation is delayed, the user-visible state must show `pending` or `temporarily unavailable` instead of pretending the action succeeded.

### Expected performance

The following targets are assumed for a small FinTech product with consumer-facing UX and internal ops workflows:

| Area | Assumed target | Rationale |
| --- | --- | --- |
| Create virtual card API | p95 <= 800 ms excluding issuer processor delay | Card creation may require external processor calls; sub-second local handling preserves good UX. |
| Freeze/unfreeze API | p95 <= 500 ms excluding issuer processor delay | Freeze is a safety action and should feel immediate. |
| Limit update API | p95 <= 400 ms | Limit validation is local policy work with a simple persisted update. |
| Transaction list API | p95 <= 700 ms for first page | Users expect recent spending to load quickly even with joins and masking. |
| Ops/compliance dashboard freshness | <= 5 minutes for derived risk signals | Near-real-time is sufficient for review queues while avoiding fragile batch pressure. |
| Pagination | Default 25 items, max 100 items | Prevents expensive reads and oversized responses. |
| Rate limits | 10 create attempts/hour/user, 30 state changes/hour/card, 60 transaction reads/min/user | Reduces abuse and accidental repeated actions without blocking normal usage. |
| Audit durability | Audit event persisted before user-visible success response | Compliance evidence must exist for every confirmed sensitive action. |

## Implementation Notes

### Domain model guardrails
- Use `card_id` for local references and `issuer_card_token` for processor references; never use PAN as an identifier.
- Represent money as integer minor units plus ISO 4217 currency code, or an exact decimal type if language conventions require it.
- Supported card states are `pending_activation`, `active`, `frozen_by_user`, `frozen_by_ops`, `closed`, and `failed_creation`.
- `closed` is terminal; no card may be unfrozen or reused after closure.
- `frozen_by_ops` can only be cleared by an authorized ops or compliance actor, not by the end user.

### API and workflow semantics
- All write commands must accept and persist an idempotency key.
- Repeating a write with the same idempotency key and same payload must return the original result.
- Repeating a write with the same idempotency key and different payload must return a conflict.
- State changes must validate current state, actor role, card ownership, and issuer processor availability before returning success.
- User-facing errors must be specific enough to guide the user but must not reveal fraud rules, internal watchlist status, or processor internals.

### Data handling
- Logs must include request IDs and high-level action names, but not card numbers, CVV, full address, full date of birth, or raw identity document values.
- Test fixtures must use synthetic users, synthetic tokens, masked card values, and fake transaction descriptors.
- Internal search should support `card_id`, `user_id`, audit event ID, and last four digits only when paired with a stronger identifier.
- Retention policy assumption: audit events retained for 7 years; non-audit operational logs retained for 90 days unless legal hold applies.

### Edge case policy
- Prefer fail-closed behavior for permission, audit, and issuer uncertainty.
- A user must never see another user's card, transaction, limit, audit event, or compliance note.
- When a flow fails after local persistence but before issuer confirmation, create a reconciliation task and show a pending or failed status instead of retrying silently forever.
- Suspected fraud signals must route to internal review and may freeze a card through `frozen_by_ops`; user-facing copy should say the card is temporarily unavailable.

## Context

### Beginning context
- `specification.md` is the source of truth for the virtual card lifecycle feature.
- `agents.md` defines AI-agent behavior for regulated FinTech implementation and review work.
- `.cursor/rules/fintech-spec-rules.md` defines editor-level rules for AI-assisted changes.
- The product operates as a regulated FinTech system requiring clear boundaries around sensitive data, auditability, and role-based operations.

### Ending context
- The virtual card feature is defined at objective, policy, workflow, edge-case, verification, and task levels.
- Future implementation work can use this specification to produce APIs, data models, user experiences, internal tools, tests, and compliance evidence.
- AI-assisted changes follow the agent and editor rules for sensitive data handling, auditability, verification, and production-grade FinTech defaults.

## Core Flows

### Create virtual card
1. End user requests a new virtual card for an eligible account.
2. System checks identity status, account status, product eligibility, card count limits, rate limits, and idempotency key.
3. System requests a tokenized card from the issuer processor.
4. System stores local card metadata, masked display details, initial state, and audit event.
5. User receives a success, pending, or failure response with no sensitive card data beyond allowed masked fields.

### Freeze or unfreeze card
1. Actor requests a state change for a card they are authorized to manage.
2. System validates actor role, ownership, current card state, issuer availability, and policy restrictions.
3. System sends the state change to the issuer processor when required.
4. System stores the resulting state and audit event before returning success.
5. User-visible state updates within the expected consistency window or shows a pending status.

### Set spending limits
1. End user submits daily and/or monthly limits for a card.
2. System validates currency, minimum and maximum values, monthly >= daily, active card ownership, and product-level caps.
3. System stores limits in minor units and emits an audit event.
4. Limit changes are visible to end user and internal staff with role-appropriate details.

### View transactions
1. End user opens the transaction list for a card they own.
2. System retrieves recent authorized, pending, posted, declined, reversed, and refunded transactions.
3. System masks merchant and card data according to policy.
4. System returns paginated results with stable sorting and empty-state messaging.

### Internal ops and compliance review
1. Authorized staff search or open a review queue item using non-sensitive identifiers.
2. System verifies staff role and records the review access event.
3. Staff can inspect card state, masked transaction summaries, audit events, and compliance-only notes.
4. Staff can flag an account, freeze a card by ops policy, or close a review item with a reason code.

## Edge Cases and Failure Modes

| Scenario | Expected user-visible behavior | Audit/compliance behavior | Related objectives |
| --- | --- | --- | --- |
| Duplicate card creation request with same idempotency key and same payload | Return original card creation result. | Record retry count or reference original audit event without creating a duplicate card. | M1, M6, M7 |
| Duplicate idempotency key with different payload | Return conflict and explain that the request cannot be reused. | Emit audit event with conflict outcome. | M1, M6, M7 |
| User exceeds allowed virtual card count | Return policy limit message without exposing risk rules. | Emit denied card creation event with policy reason code. | M1, M6 |
| Concurrent freeze and unfreeze requests | Resolve with serialized state transition; return current final state. | Store both attempted actions with final accepted/rejected outcomes. | M2, M6, M7 |
| User tries to unfreeze `frozen_by_ops` card | Show card is temporarily unavailable and direct user to support. | Emit denied user unfreeze event; retain ops freeze reason internally. | M2, M5, M6 |
| Invalid daily or monthly limit | Return validation error for the specific invalid field. | Audit only if the request reaches authenticated command handling; do not store new limit. | M3, M7 |
| Monthly limit lower than daily limit | Return validation error explaining monthly must be greater than or equal to daily. | Emit validation failure event with non-sensitive values. | M3, M6 |
| Transaction list has no records | Show empty state for the selected card and period. | No compliance action required beyond normal access logging. | M4 |
| Stale transaction data from processor | Show last updated timestamp and avoid claiming final settlement. | Mark source freshness in internal diagnostics. | M4, M7 |
| User attempts to access another user's card | Return not found or unauthorized according to existing security policy. | Emit permission violation event and risk signal. | M5, M6, M7 |
| Suspicious rapid card creation or freeze/unfreeze pattern | Apply rate limit or route to review with neutral user-facing copy. | Create risk signal and review queue item. | M5, M6, M7 |
| Issuer processor unavailable during freeze | Show pending or unavailable status; do not claim freeze succeeded until confirmed. | Emit external dependency failure event and create reconciliation task. | M2, M6, M7 |
| Audit event persistence fails | Do not return success for sensitive write action. | Raise operational alert; retry through controlled recovery path. | M6, M7 |
| Internal support user lacks compliance permission | Hide compliance notes and investigation reason fields. | Emit denied privileged access event. | M5, M6 |

## Verification Strategy

| Objective | Verification approach | Acceptance signal |
| --- | --- | --- |
| M1 | Unit tests for eligibility and idempotency; integration tests with mocked issuer processor; product review of card count policy. | Eligible users create cards once per valid request; duplicate retries do not duplicate cards. |
| M2 | State machine tests; concurrency tests; role-based integration tests for user and ops freezes. | Invalid transitions are rejected; `frozen_by_ops` cannot be cleared by users. |
| M3 | Validation tests for currency, minor units, min/max limits, monthly-vs-daily rules, and inactive cards. | Limits store exactly and display consistently without floating-point rounding defects. |
| M4 | Transaction fixture tests for empty, pending, posted, declined, reversed, and refunded records; pagination tests. | Transaction pages are stable, masked, sorted, and bounded by max page size. |
| M5 | RBAC tests and manual compliance review checklist for internal views. | Support and compliance roles see only fields permitted by policy. |
| M6 | Audit event contract tests; log scanning for sensitive data; retention review. | Every sensitive action has an audit event and no full PAN/CVV appears in logs or fixtures. |
| M7 | Failure injection for issuer outage, audit failure, stale reads, and duplicate writes. | System fails closed, preserves evidence, and returns safe user-facing responses. |

## Low-Level Tasks

### 1. Define virtual card domain model and states

What prompt would you run to complete this task?
Create the virtual card domain model for a regulated FinTech app, including card identifiers, masked display fields, state machine, ownership, limit references, issuer token references, and audit metadata.

What file do you want to CREATE or UPDATE?
Hypothetical domain model documentation or application model file.

What function do you want to CREATE or UPDATE?
Virtual card entity, state enum, and state transition validation.

What are details you want to add to drive the code changes?
- Use `card_id`, `user_id`, and `issuer_card_token`; never model PAN or CVV as stored fields.
- Include states `pending_activation`, `active`, `frozen_by_user`, `frozen_by_ops`, `closed`, and `failed_creation`.
- Include created, updated, and closed timestamps.
- Acceptance criteria: the state model prevents reopening `closed` cards and prevents user actors from clearing `frozen_by_ops`.

### 2. Specify card creation workflow

What prompt would you run to complete this task?
Implement a card creation command that validates user eligibility, product policy, card count, idempotency, issuer processor response, local persistence, and audit logging.

What file do you want to CREATE or UPDATE?
Hypothetical card creation service or workflow specification.

What function do you want to CREATE or UPDATE?
Create virtual card command handler.

What are details you want to add to drive the code changes?
- Require an idempotency key for every create request.
- Deny creation when identity verification, account status, product status, or card count policy fails.
- Store only tokenized and masked issuer response fields.
- Acceptance criteria: duplicate retries return the original result; conflicting retries return conflict; success is not returned unless audit event persistence succeeds.

### 3. Specify freeze and unfreeze workflow

What prompt would you run to complete this task?
Implement freeze and unfreeze commands with role-aware validation, issuer processor synchronization, serialized state transitions, idempotent retries, and audit events.

What file do you want to CREATE or UPDATE?
Hypothetical card state service or workflow specification.

What function do you want to CREATE or UPDATE?
Freeze card command handler and unfreeze card command handler.

What are details you want to add to drive the code changes?
- End users may freeze and unfreeze only their own cards unless the card is `frozen_by_ops`.
- Ops and compliance actors may apply `frozen_by_ops` with reason codes.
- Concurrent requests must serialize and return the final accepted state.
- Acceptance criteria: freeze returns confirmed, pending, or failed state honestly; unauthorized unfreeze attempts are rejected and audited.

### 4. Specify spending limit validation

What prompt would you run to complete this task?
Implement spending limit management for daily and monthly card limits with exact money handling, product caps, validation errors, and audit logging.

What file do you want to CREATE or UPDATE?
Hypothetical card limit service or policy specification.

What function do you want to CREATE or UPDATE?
Set card limits command handler and limit validation policy.

What are details you want to add to drive the code changes?
- Store limits as minor units and ISO currency code.
- Validate daily and monthly minimums, maximums, and monthly >= daily.
- Reject unsupported currencies and inactive or closed cards.
- Acceptance criteria: invalid fields return field-specific errors; accepted limits display exactly as stored; every accepted change is audited.

### 5. Specify transaction listing behavior

What prompt would you run to complete this task?
Implement a transaction list view for a user's virtual card with pagination, sorting, masking, empty states, pending states, and stale-data indicators.

What file do you want to CREATE or UPDATE?
Hypothetical transaction read service or transaction view specification.

What function do you want to CREATE or UPDATE?
List card transactions query handler.

What are details you want to add to drive the code changes?
- Default page size is 25 and maximum page size is 100.
- Sort by posted timestamp descending, then transaction ID for stable ordering.
- Include statuses `pending`, `posted`, `declined`, `reversed`, and `refunded`.
- Acceptance criteria: empty results return a clear empty state; no full card data appears in transaction responses.

### 6. Specify internal ops and compliance review

What prompt would you run to complete this task?
Implement an internal review view that allows authorized staff to search by safe identifiers, inspect masked card and transaction summaries, review audit events, and record compliance-only notes.

What file do you want to CREATE or UPDATE?
Hypothetical internal ops/compliance specification.

What function do you want to CREATE or UPDATE?
Internal card review query and review action handlers.

What are details you want to add to drive the code changes?
- Support search by `card_id`, `user_id`, audit event ID, and controlled last-four lookup.
- Separate support-visible notes from compliance-only notes.
- Require reason codes for ops freezes and review closures.
- Acceptance criteria: support users cannot view compliance-only fields; every internal access and action is audited.

### 7. Specify audit event contract

What prompt would you run to complete this task?
Define and implement an append-only audit event contract for all card lifecycle, limit, transaction access, and internal review actions.

What file do you want to CREATE or UPDATE?
Hypothetical audit event contract or compliance logging specification.

What function do you want to CREATE or UPDATE?
Audit event writer and audit event schema.

What are details you want to add to drive the code changes?
- Include actor, subject, action, outcome, card ID, request ID, idempotency key, timestamp, source channel, and policy reason code.
- Exclude full PAN, CVV, raw identity values, and unrestricted free-text sensitive data.
- Persist audit events before returning success for sensitive writes.
- Acceptance criteria: audit event tests cover success, denial, conflict, processor failure, and internal review access.

### 8. Specify RBAC and sensitive-data boundaries

What prompt would you run to complete this task?
Implement role-based access control and sensitive-data filtering for end-user, support, compliance, ops manager, and system actors.

What file do you want to CREATE or UPDATE?
Hypothetical authorization policy or security specification.

What function do you want to CREATE or UPDATE?
Authorization policy evaluator and response masking policy.

What are details you want to add to drive the code changes?
- Deny cross-user access by default.
- Require elevated permission for compliance notes, ops freezes, and risk review actions.
- Mask all card details consistently across user and internal responses.
- Acceptance criteria: permission tests prove each role can access only the intended actions and fields.

### 9. Specify failure handling and reconciliation

What prompt would you run to complete this task?
Implement failure handling for issuer processor outages, partial persistence failures, stale reads, audit write failures, and retryable reconciliation tasks.

What file do you want to CREATE or UPDATE?
Hypothetical reliability and reconciliation workflow specification.

What function do you want to CREATE or UPDATE?
External dependency error handler and reconciliation task creator.

What are details you want to add to drive the code changes?
- Return pending or unavailable states when issuer confirmation is missing.
- Do not return success for sensitive writes if audit persistence fails.
- Create reconciliation tasks for local/issuer state mismatches.
- Acceptance criteria: failure injection tests demonstrate fail-closed behavior and no silent success on partial failure.

### 10. Specify verification fixtures and review checklist

What prompt would you run to complete this task?
Create test fixtures, verification scenarios, and a compliance review checklist for the virtual card lifecycle feature.

What file do you want to CREATE or UPDATE?
Hypothetical test plan or QA/compliance checklist document.

What function do you want to CREATE or UPDATE?
Not applicable; this is a verification artifact.

What are details you want to add to drive the code changes?
- Include synthetic users, synthetic card tokens, masked card data, and transaction examples for all supported statuses.
- Include review checks for logging, audit completeness, permission boundaries, stale data, and fraud-ish patterns.
- Include performance tests for the assumed p95 latency and pagination targets.
- Acceptance criteria: every mid-level objective maps to at least one automated or manual verification item.
