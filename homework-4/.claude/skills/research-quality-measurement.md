---
name: research-quality-measurement
description: >-
  Defines a standard scale and rubric for measuring the quality of codebase
  research. Use when verifying a Bug Researcher's output (research/codebase-research.md)
  and writing research/verified-research.md. Provides quality levels, scoring
  rules, and the required result-file format the Bug Research Verifier must follow.
---

# Research Quality Measurement

A rubric for grading how trustworthy a piece of codebase research is, so the
**Bug Research Verifier** can assign a consistent, defensible **Research Quality**
label and the **Bug Planner** downstream knows how much to trust it.

Apply this skill whenever you verify `research/codebase-research.md` and produce
`research/verified-research.md`.

---

## 1. What gets measured

Every research document makes a set of **claims**. A claim is any verifiable
statement, typically one of:

- A **file:line reference** ("the bug is in `src/auth.js:42`").
- A **code snippet** quoted from the source.
- A **behavioral assertion** ("this function returns `null` on empty input").
- A **causal/diagnosis claim** ("the crash happens because `x` is unvalidated").

You verify each claim against the actual source and classify it:

| Status | Meaning |
|--------|---------|
| ✅ **Verified** | Reference resolves, snippet matches source exactly (modulo whitespace), assertion is true. |
| ⚠️ **Partial** | Mostly correct but imprecise — e.g. line off by a few, snippet paraphrased, minor detail wrong. |
| ❌ **False** | Reference does not exist, snippet does not match, or assertion is wrong. |
| ❓ **Unverifiable** | Cannot be checked (file missing, claim too vague, external dependency). |

---

## 2. Quality levels

Assign exactly **one** overall level using the scoring below.

| Level | Label | Meaning | Planner guidance |
|-------|-------|---------|------------------|
| **L5** | 🟢 **Excellent** | All claims verified; references exact; snippets match; diagnosis sound. | Use as-is. |
| **L4** | 🟢 **Good** | All critical claims verified; only minor cosmetic imprecisions. | Use with minor caution. |
| **L3** | 🟡 **Adequate** | Core diagnosis correct but several imprecise references or partial matches. | Spot-check before planning. |
| **L2** | 🟠 **Weak** | Important claims false or unverifiable; diagnosis questionable. | Re-research key parts. |
| **L1** | 🔴 **Unreliable** | Core claims false; references broken; cannot be trusted. | Reject — redo research. |

### Scoring rule

1. Compute the **verification rate** = `Verified / Total claims`.
2. Identify **critical claims** — those the proposed fix depends on (the buggy
   location and the root-cause diagnosis).
3. Map to a level:

   - **L5** — 100% verified, including all critical claims.
   - **L4** — ≥ 90% verified, **all critical claims verified**, remaining issues cosmetic only.
   - **L3** — ≥ 75% verified **and** all critical claims at least Partial.
   - **L2** — ≥ 50% verified **or** one critical claim False/Unverifiable.
   - **L1** — < 50% verified **or** the root-cause diagnosis is False.

> A single **False critical claim caps the level at L2**, regardless of the
> verification rate. The whole point of research is to be right about the bug.

### Pass/fail

- **PASS** = level **L3 or higher** (research is usable by the Bug Planner).
- **FAIL** = level **L2 or lower** (research must be revised before planning).

---

## 3. Required result-file format

When you write `research/verified-research.md`, it **must** contain these
sections, in this order:

```markdown
# Verified Research: <bug id / short title>

## Verification Summary
- **Result:** PASS | FAIL
- **Research Quality:** L<n> — <Label>   (per research-quality-measurement skill)
- **Claims:** <verified>/<total> verified (<partial> partial, <false> false, <unverifiable> unverifiable)
- **Verified by / date:** <agent> — <YYYY-MM-DD>

## Verified Claims
| # | Claim | Reference (file:line) | Status | Note |
|---|-------|-----------------------|--------|------|
| 1 | ...   | src/...:NN             | ✅     | snippet matches source |

## Discrepancies Found
<List each Partial / False / Unverifiable claim with: what the research said,
what the source actually shows, and the impact. "None." if there are none.>

## Research Quality Assessment
- **Level:** L<n> — <Label>
- **Verification rate:** <x>%
- **Critical claims:** <status of each critical claim>
- **Reasoning:** <why this level was assigned, citing the scoring rule>

## References
<Every source location you checked, as file:line, so the assessment is reproducible.>
```

---

## 4. Verification procedure

1. Read `research/codebase-research.md` and extract every claim.
2. For each claim, open the cited source and check the reference and snippet
   **against the real file** — never trust the research's own quote.
3. Mark each claim ✅ / ⚠️ / ❌ / ❓ and record the discrepancy if not ✅.
4. Flag which claims are **critical** (the fix depends on them).
5. Compute verification rate, apply the scoring rule, derive the level and
   PASS/FAIL.
6. Write `verified-research.md` in the exact format above.

## 5. Rules

- **Quote the source, not the research.** Always re-open the file.
- **Be exact about references.** An off-by-N line number is a Partial, not a
  Verified — note the correct line.
- **Critical claims dominate.** Getting the bug location wrong is worse than ten
  cosmetic slips.
- **State reasoning explicitly** so the level is auditable and reproducible.
- **Do not fix code or write the plan** — this skill only measures and reports.
