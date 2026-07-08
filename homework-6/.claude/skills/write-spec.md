---
name: write-spec
description: Generate homework-6/specification.md for the banking transaction-processing pipeline from the bundled template
---

# Generate the pipeline specification

Author `homework-6/specification.md` for the banking transaction-processing pipeline (Task 1 / Agent 1), following the bundled template and the structure mandated in `TASKS.md`. **Write a specification only — no implementation code.**

Scope for this run (optional): `$ARGUMENTS`

## Steps

1. **Read the inputs, in order:**
   - `.claude/agents/specification-writer/specification-TEMPLATE-example.md` — the template shape (prefer the **Banking-Specific** variant).
   - `TASKS.md` — Task 1 defines the mandatory `specification.md` sections; the rest defines the four agents to decompose into low-level tasks.
   - `sample-transactions.json` — the beginning-state input. Read every row; it contains the edge cases the spec must anticipate.

2. **Draft `specification.md` with exactly these sections (from TASKS.md Task 1):**
   1. **High-Level Objective** — one sentence + one-sentence scope boundary.
   2. **Mid-Level Objectives** — 4–5 observable/testable items, each with a stable ID (`M1`, `M2`, …).
   3. **Implementation Notes** — decimal money (`decimal.Decimal`, never `float`), ISO 4217 currency validation, ISO 8601 audit trail (timestamp, agent name, transaction ID, outcome), PII (account numbers/names) never logged in plaintext, file-based JSON message protocol, idempotent/deterministic writes.
   4. **Context** — Beginning: `sample-transactions.json` + empty `shared/` tree. Ending: results in `shared/results/`, a pipeline summary report, test coverage ≥ 90%.
   5. **Low-Level Tasks** — **one entry per pipeline agent** (Transaction Validator, Fraud Detector, a third agent such as Compliance Checker, the Integrator/orchestrator, **and a Frontend / Web UI agent**), each citing the `M#` it serves and using **exactly** this format:
      ```
      Task: [Agent Name] (serves: M#)
      Prompt: "[Exact prompt you will give Claude Code or Copilot]"
      File to CREATE: agents/[agent_name].py
      Function to CREATE: process_message(message: dict) -> dict
      Details: [What the agent checks, transforms, or decides]
      ```
      The **Frontend / Web UI** task targets `frontend/server.py` (FastAPI) + a static HTML/JS page (not `process_message`); its Details cover submitting sample transactions into the pipeline and showing each transaction's real-time state/lifecycle from the `shared/` directories. These Low-Level Tasks are the input contract for **Agent 2 (`code-generator`)**, which routes each to a matching nested subagent — so keep task names and file paths precise.

3. **Integrate the cross-cutting depth** (do not relegate to a single bullet):
   - **Edge-case table** with expected behavior (user/ops-visible outcome + audit/compliance implication), grounded in the real sample data: invalid currency `XYZ` (TXN006), negative refund (TXN007), off-hours 02:47 (TXN004), high-value wires (TXN002/TXN005), boundary $9,999.99 vs. the $10k rule (TXN003), plus missing fields, duplicate `transaction_id`, partial/unreadable JSON, and audit-write failure.
   - **Verification** — a method per mid-level objective; acceptance criteria / definition-of-done on several low-level tasks.
   - **Performance** — measurable targets (per-transaction latency, batch size, throughput, read-after-write consistency); label hypotheticals as **assumed targets** and justify them.

4. **Apply the Python + regulated-banking safe defaults** throughout: fail-closed authorization and audit, no PII/PAN in any example, synthetic/masked data only, no vague wording ("secure enough", "fast", "handle errors").

5. **Write the result to `homework-6/specification.md`**, then report a short summary and any assumptions made.

## Notes

- For a fully autonomous, end-to-end run you may dispatch the **`specification-writer`** subagent, which encodes this same method and self-verifies against a checklist.
- Self-check before finishing: all 5 sections present; 4–5 `M#` objectives; one correctly-formatted low-level task per agent; edge-case table tied to the sample data; a verification method per objective; performance targets measurable and labeled.
