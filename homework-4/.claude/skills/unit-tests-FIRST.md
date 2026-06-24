---
name: unit-tests-FIRST
description: >-
  Defines the FIRST principles for unit tests — Fast, Independent, Repeatable,
  Self-validating, Timely. Use when generating or reviewing unit tests for
  changed code (the Unit Test Generator producing tests/ and test-report.md).
  Provides a per-principle definition, do/don't rules, an enforcement checklist,
  and the required test-report.md format the generator must follow.
---

# Unit Tests: FIRST

A standard for what makes a unit test *good*, so the **Unit Test Generator** writes
tests that are trustworthy and maintainable, and downstream readers of
`test-report.md` know the tests satisfy a consistent bar.

Apply this skill whenever you generate unit tests for changed code and produce
`test-report.md`. Every test you write must satisfy **all five** FIRST principles.

---

## 1. The five principles

| Letter | Principle | One-line definition |
|--------|-----------|---------------------|
| **F** | **Fast** | Each test runs in milliseconds; the suite runs fast enough to be run constantly. |
| **I** | **Independent** | Tests do not depend on each other or on execution order; each sets up its own state. |
| **R** | **Repeatable** | Same result every run, on any machine, with no external/environmental dependency. |
| **S** | **Self-validating** | The test asserts its own pass/fail — no manual inspection of output or logs. |
| **T** | **Timely** | Tests are written alongside (or right after) the code they cover, for the change at hand. |

---

### F — Fast

A unit test exercises one unit of behavior in isolation and should complete in
milliseconds. A slow suite gets run rarely, which defeats the purpose.

**Do**
- Test pure logic in memory; isolate the unit under test.
- Replace slow collaborators (network, disk, DB, sleeps, time) with stubs/fakes/mocks.

**Don't**
- Make real network calls, hit a real database, or touch the filesystem unnecessarily.
- Use real `sleep`/timers or large data-driven loops for what a small case proves.

**Smell:** a single test taking > ~100ms, or the suite taking many seconds, usually
means it is not a unit test.

---

### I — Independent

Each test stands alone: it creates the state it needs and cleans up after itself.
Running tests in any order, or running just one, must give the same result.

**Do**
- Build fresh fixtures per test (setup/`beforeEach`); avoid shared mutable globals.
- Make each test assert one behavior so failures point to one cause.

**Don't**
- Rely on a value left behind by an earlier test, or on test execution order.
- Share mutable module/global state between tests without resetting it.

**Smell:** tests pass together but fail in isolation (or vice versa), or reordering
breaks them.

---

### R — Repeatable

A test produces the same verdict every time, on any machine, offline, regardless of
clock, locale, or environment.

**Do**
- Inject or freeze time, randomness, UUIDs, and locale-sensitive formatting.
- Eliminate dependence on external services, ports, ambient env vars, or network.

**Don't**
- Assert on `Date.now()`/`new Date()`, `Math.random()`, or current timezone directly.
- Depend on test data that changes over time or on resources you don't control.

**Smell:** a "flaky" test — green sometimes, red other times, with no code change.

---

### S — Self-validating

The test decides pass/fail by itself through assertions. No human reads console
output, diffs files by hand, or interprets logs to know whether it passed.

**Do**
- Assert concrete expected values/outcomes (including expected errors/exceptions).
- Make the assertion specific so a failure message explains what went wrong.

**Don't**
- `console.log`/`print` a value and expect a human to verify it.
- Write tests with no assertion, or assertions so loose they can't fail.

**Smell:** a test with no assertions, or one that only checks "did not throw" when a
real value should be verified.

---

### T — Timely

Tests are written for the change at hand, close in time to the code — ideally just
before or just after. In this pipeline that means: cover the **new/changed** code
described in `fix-summary.md`, not the whole codebase, and not someday-later.

**Do**
- Generate tests for the changed/added behavior while the change is fresh.
- Cover the bug the fix addressed (a regression test) plus key paths of new code.

**Don't**
- Defer testing or leave changed code uncovered.
- Spend the budget regenerating tests for untouched, already-covered code.

**Smell:** changed code merged with no accompanying test, or tests that only cover
code nobody touched in this change.

---

## 2. Enforcement checklist

Before recording a generated test as done, confirm **every** box for **each** test:

- [ ] **F** — No real I/O (network/DB/disk/sleep); collaborators stubbed; runs in ms.
- [ ] **I** — Self-contained setup; no shared mutable state; order-independent; one behavior.
- [ ] **R** — Time/randomness/locale/env controlled; no external dependency; deterministic.
- [ ] **S** — Has explicit assertions that can fail; expected values are concrete.
- [ ] **T** — Targets new/changed code from `fix-summary.md`; includes a regression test for the fixed bug.

If any box can't be checked, fix the test (or its design) before reporting it.

---

## 3. Required result-file format

When you write `test-report.md`, it **must** contain these sections, in this order:

```markdown
# Test Report: <change id / short title>

## Summary
- **Result:** PASS | FAIL
- **Framework / command:** <e.g. Jest — `npm test`>
- **Scope:** <changed files/functions covered>
- **Tests:** <total> total — <passed> passed, <failed> failed, <skipped> skipped
- **Generated by / date:** <agent> — <YYYY-MM-DD>

## Tests Generated
| # | Test file | Covers (unit / behavior) | Type (happy/edge/regression) | Result |
|---|-----------|--------------------------|------------------------------|--------|
| 1 | tests/...  | src/...::fn               | regression                   | ✅     |

## FIRST Compliance
| Principle | Status | Note (how it is satisfied / any caveat) |
|-----------|--------|------------------------------------------|
| Fast            | ✅ | no I/O, suite runs in <Ns> |
| Independent     | ✅ | fresh fixtures per test |
| Repeatable      | ✅ | time/randomness controlled |
| Self-validating | ✅ | explicit assertions |
| Timely          | ✅ | covers changed code + regression for the fix |

## Test Run Output
<the actual runner output: pass/fail counts and any failures, quoted verbatim>

## Coverage of Changed Code
<which changed functions/branches are covered, and any gaps left untested with reason>

## References
<changed files (file:line) and the test files created, so the report is reproducible.>
```

---

## 4. Generation procedure

1. Read `fix-summary.md` and the changed files; list the new/changed units and the
   bug the fix addressed.
2. Detect the project's test framework and conventions (existing `tests/`, config,
   `package.json` scripts); match them — do not introduce a new framework.
3. For each changed unit, write tests covering happy path, edge cases, and a
   **regression test** for the fixed bug. Stub external collaborators.
4. Run each test through the **FIRST enforcement checklist** (section 2) and fix any
   violations.
5. Run the suite with the project's test command and capture the real output.
6. Write `test-report.md` in the exact format above.

## 5. Rules

- **All five, every test.** A test that violates one FIRST principle is not done.
- **Changed code only.** Cover what the fix touched; don't re-test untouched code.
- **Always include a regression test** for the bug the fix resolved.
- **Match the project's framework and style** — never invent a new one.
- **Report the real run output**, including failures; never fabricate a green result.
- **Generate and run tests only** — do not modify the application source code.
