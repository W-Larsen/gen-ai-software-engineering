# Security Report

## Summary
- Date: 2026-06-24
- Scope: Changed files for bug set 001 — `src/evaluate.js` (SEC-001), `src/calc.js` (BUG-001, BUG-002). Reviewed alongside `src/index.js` (data-flow entry point) and `package.json` (dependencies) for context.
- Overall risk: LOW
- Findings count by severity: CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 1, INFO: 2

## Findings

### [LOW] Unbounded recursion in expression parser allows stack-exhaustion DoS
- File: `src/evaluate.js:46-83` (`parseExpression` / `parseTerm` / `parseFactor`)
- Class: Missing input validation / Denial of Service (CWE-674, Uncontrolled Recursion)
- Description: The recursive-descent parser recurses once per nested `(`. The allowlist permits an arbitrary number of parentheses, and there is no limit on input length or nesting depth. An input such as a long run of `(` characters (e.g. `"(".repeat(100000) + "1" + ")".repeat(100000)`) drives recursion deep enough to throw a `RangeError: Maximum call stack size exceeded`, crashing the process.
- Exploit scenario: In the current CLI usage the input is the user's own `argv`, so the trust boundary is minimal (a user can only crash their own invocation). Impact rises to a real availability concern if `evaluateExpression` is ever reused behind a network/server boundary or fed expressions from another user. The crash is caught by `main()`'s try/catch in `src/index.js` only if it surfaces as a normal throw; a stack overflow `RangeError` is catchable, so the CLI exits with an error rather than an uncatchable abort — limiting impact today.
- Recommendation: Enforce a maximum input length and/or a maximum recursion/parenthesis-nesting depth before or during parsing (e.g. reject expressions longer than a few hundred characters, or track and cap nesting depth and throw a normal `Error`). Do not implement here — described only.

### [INFO] Stale/misleading security documentation left in source
- File: `src/evaluate.js:5-17`
- Class: Documentation hygiene / defense-in-depth
- Description: The file header still states the file "ships in the 'before' (insecure) state" and the `evaluateExpression` docstring still claims "the untrusted CLI input is passed straight to eval()". After the SEC-001 fix this is no longer true — `eval()` has been removed. Stale comments that describe a vulnerability as present can mislead future reviewers and risk an incorrect "revert to original" during refactors.
- Exploit scenario: Not directly exploitable.
- Recommendation: Update the header and docstring to reflect the parser-based implementation and that SEC-001/CWE-95 has been remediated.

### [INFO] Error messages echo attacker-influenced token text
- File: `src/evaluate.js:80` and propagation via `src/index.js:68`
- Class: Information handling / output encoding
- Description: `parseFactor` builds an error message containing the offending token (`Invalid expression: unexpected token "${token}"`), which is printed to stderr. Because tokens are constrained by the upstream allowlist (`[0-9.\s+\-*/()]`), no dangerous characters (quotes, control chars, shell metacharacters, or markup) can reach the message, so there is no log-injection, format-string, or terminal-escape risk in the current design. Noted only as a defense-in-depth observation should the allowlist ever be widened.
- Exploit scenario: Not exploitable under the current allowlist.
- Recommendation: If the allowlisted character set is ever expanded, sanitize/escape interpolated token text before including it in error output or logs.

## Verification of fix-summary.md claims

- **SEC-001 (eval → recursive-descent parser): CONFIRMED REMEDIATED.** The on-disk `src/evaluate.js` matches the "After" block in the fix-summary. The `eval(expr)` call and its `// eslint-disable-line no-eval` annotation are gone. The new implementation:
  1. Rejects non-string input (`TypeError`).
  2. Applies a strict full-string allowlist `^[0-9.\s+\-*/()]+$`, rejecting any letters, quotes, dots-as-property-access, backticks, or call syntax — so payloads like `process.exit(1)` and `require('child_process').execSync('id')` are rejected before any evaluation.
  3. Tokenizes and evaluates via a hand-written recursive-descent parser that only ever performs the four arithmetic operations on parsed numbers. There is no `eval`, `Function`, `vm`, `setTimeout(string)`, or other dynamic-code sink anywhere in the module.
  CWE-95 (eval injection) / arbitrary code execution is genuinely eliminated — this is a true fix, not a filter that still funnels input into an interpreter. The allowlist + parser are independent defenses (input would have to pass the regex AND parse as valid arithmetic), so even a regex weakness could not reach code execution.
- **ReDoS check:** Both regexes (`^[0-9.\s+\-*/()]+$` and `\d+(?:\.\d+)?|[+\-*/()]`) use simple character classes with linear quantifiers and no nested/overlapping repetition, so they are not vulnerable to catastrophic backtracking.
- **Division-by-zero guard:** Present (`src/evaluate.js:61-63`) and uses strict `=== 0`; behaves as documented.
- **BUG-001 (`average` empty-array guard): CONFIRMED.** `src/calc.js:30` adds `if (numbers.length === 0) return 0;`. Pure arithmetic; no security impact.
- **BUG-002 (`applyDiscount` formula): CONFIRMED.** `src/calc.js:45` now computes `price - (price * percent) / 100`. Pure arithmetic; no security impact.
- **Dependencies:** `package.json` declares zero runtime/dev dependencies and none were added by the change, so there is no new supply-chain exposure (no unpinned, vulnerable, or untrusted packages introduced).

## Notes & Limitations
- No `git` shell access was available in this environment; changed files were identified from `fix-summary.md` and confirmed by reading the on-disk source, which matches the documented "After" state byte-for-byte. If other files were modified outside the documented scope, they were not reviewed.
- XSS and CSRF were assessed as not applicable: this is a local Node.js CLI with no HTML rendering, browser context, cookies, or HTTP endpoints. There is no web trust boundary in the changed code.
- No hardcoded secrets, credentials, or high-entropy strings were found in the reviewed files.
- No insecure-comparison/timing-attack surface exists in the changed code (no secret/token/HMAC comparisons are performed).
- A dedicated dependency vulnerability scan (e.g. `npm audit`) was not run; given the zero-dependency manifest the residual supply-chain risk is negligible, but running it in CI is still recommended as standard practice.
- The single LOW finding (recursion DoS) is the only actionable security item; it is hardening rather than a directly exploitable flaw under the current CLI trust model.
