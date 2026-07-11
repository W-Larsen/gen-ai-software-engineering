# Research Notes

## Query: Python decimal.Decimal quantize rounding modes for currency minor units
- Search: python decimal Decimal quantize ROUND_HALF_EVEN currency minor unit
- context7 library ID: context7 MCP tool was not available in this session's toolset; intended
  target library ID is `/python/cpython` (stdlib `decimal` module documentation).
- Applied: Confirmed that `Decimal.quantize(exp, rounding=ROUND_HALF_EVEN)` is the correct way to
  round monetary amounts to a currency's ISO 4217 minor-unit exponent (banker's rounding, avoids
  systematic bias vs. `ROUND_HALF_UP`), and that `Decimal.quantize` preserves the operand's sign.
  This is why `agents/transaction_validator.py` calls `protocol.quantize_amount(decimal_amount,
  currency)` *before* applying the negative-amount/refund rule (`abs()` on the already-quantized
  value) rather than rounding after sign-flipping, keeping TXN007's canonical amount exactly
  `Decimal("100.00")` regardless of rounding-mode edge cases at the last minor-unit digit. Also
  confirmed `Decimal(str(x))` (never `Decimal(float)`) is the correct construction path to avoid
  binary-float imprecision entering the pipeline, matching `protocol.to_decimal`'s guard that
  re-stringifies any accidental `float` input before parsing.

## Query: ISO 4217 currency code validation approaches in Python (static table vs. pycountry)
- Search: ISO 4217 currency code validation python pycountry static list
- context7 library ID: context7 MCP tool was not available in this session's toolset; intended
  target reference is the ISO 4217 standard table (no external package such as `pycountry` is a
  project dependency here).
- Applied: Verified the design decision already encoded in `agents/protocol.py`
  (`CURRENCY_MINOR_UNITS` / `ISO_4217_CURRENCIES` as a static, versioned dict rather than an
  external service/package call) is consistent with the spec's "no live external dependencies in
  v1" constraint. `agents/transaction_validator.py` reuses
  `protocol.is_valid_currency(currency)` unchanged rather than introducing a second validation
  path, so `XYZ` (TXN006) is rejected with `reason="invalid_currency_code:XYZ"` purely from the
  shared static table -- no downstream agent re-validates currency, per the spec.

## Query: Python datetime/timezone handling for deterministic "off-hours" UTC-hour scoring
- Search: python datetime aware UTC timezone hour extraction fromisoformat trailing Z ISO 8601
- context7 library ID: context7 MCP tool was not available in this session's toolset (no `mcp.json`
  entry configured); intended target library ID is `/python/cpython` (stdlib `datetime` module
  documentation, `datetime.fromisoformat`/`timezone` docs).
- Applied: Confirmed that comparing the fraud detector's off-hours window against `dt.hour` is only
  deterministic if `dt` is first normalized to an *aware* UTC datetime (never a naive local-clock
  read), which is exactly what `protocol.parse_timestamp` already does (`fromisoformat` after
  stripping a trailing `Z`, then `.astimezone(timezone.utc)`). `agents/fraud_detector.py` therefore
  calls `protocol.parse_timestamp(data["timestamp"]).hour` rather than re-parsing timestamps itself,
  so TXN004's `02:47:00Z` reliably falls inside the configured `[off_hours_start_hour,
  off_hours_end_hour)` half-open window (`[0, 6)`) regardless of the host machine's local timezone
  -- avoiding the classic bug of comparing an off-hours window against `datetime.now()`/naive local
  time instead of the message's own UTC timestamp.

## Query: Decimal comparison semantics for a fixed monetary threshold (boundary safety)
- Search: python decimal.Decimal comparison operators exact boundary >= threshold no float
- context7 library ID: context7 MCP tool was not available in this session's toolset; intended
  target library ID is `/python/cpython` (stdlib `decimal` module documentation).
- Applied: Verified `Decimal(str(x))` construction (via `protocol.to_decimal`) gives exact decimal
  comparisons with no binary-float rounding error, so `Decimal("9999.99") >= Decimal("10000.00")`
  is reliably `False` and the high-value signal in `score_transaction` never fires for TXN003's
  boundary amount. This confirmed the fraud detector should compare `protocol.to_decimal(amount)`
  directly against `rules["high_value_threshold"]` (itself parsed once via `protocol.to_decimal` in
  `load_rules`) rather than re-deriving a float threshold from the JSON config, keeping the
  boundary check exact end-to-end.

## Query: Python frozenset membership checks for a static blocked-account/sanctions list
- Search: python frozenset membership check O(1) blocklist screening best practice
- context7 MCP tool was not available in this session's toolset (no MCP entry configured for it);
  intended target library ID is `/python/cpython` (stdlib `stdtypes`/`set` documentation). Backed
  up with a live web search (see Sources below) confirming current (2026) guidance.
- Applied: Confirmed that an immutable, hashable `frozenset` (built once at import time from
  `agents/config/blocked_accounts.json`) is the correct data structure for the compliance checker's
  blocked/sanctioned-account screen -- O(1) average-case `in` membership testing versus an O(n)
  list scan, and immutability documents the intent that the loaded blocklist must not be mutated
  at runtime between transactions. `agents/compliance_checker.py`'s `load_blocked_accounts()`
  therefore returns `frozenset(str(a).strip() for a in raw["blocked_accounts"])` and
  `screen_transaction` checks `source_account in blocked_accounts or destination_account in
  blocked_accounts` directly, mirroring the same "load once, compare via `in` against a frozenset"
  pattern `agents/fraud_detector.py` already uses for `rules["home_countries"]`, keeping the
  blocked-account rule consistent with the cross-border rule's data-structure choice.

Sources:
- [Python Frozenset: Complete Guide for Beginners (2026)](https://www.upgrad.com/blog/python-frozenset/)
- [Python frozenset: Overview and Examples • datagy](https://datagy.io/python-frozenset/)
- [frozenset | Python's Built-in Data Types – Real Python](https://realpython.com/ref/builtin-types/frozenset/)

## Query: FastAPI serving a static HTML page and reading an optional JSON request body
- Search: FastAPI serve static HTML file FileResponse BackgroundTasks pattern
- context7 MCP tool was not available in this session's toolset (no `mcp.json` entry configured
  for it); intended target library ID is `/tiangolo/fastapi` (the official FastAPI docs cover
  `FileResponse`, `StaticFiles` mounting, and reading a request body directly via `Request.json()`).
  Backed up with a live web search (see Sources below) confirming the current (2026) recommended
  patterns.
- Applied: Confirmed `fastapi.responses.FileResponse` is the correct way to serve a single
  self-contained static page from `GET /` without a templating engine or build step, so
  `frontend/server.py`'s `index()` handler returns `FileResponse(str(STATIC_DIR / "index.html"))`
  directly rather than reading/echoing the file as a string response (`FileResponse` streams the
  file and sets `Content-Type` correctly). Also mounted `StaticFiles(directory=STATIC_DIR)` at
  `/static` for any future non-inline assets, matching the documented `app.mount("/static", ...)`
  pattern. For `POST /submit`, rather than declaring a `pydantic.BaseModel` request-body parameter
  (which raises a `422` when the client posts an empty body), the handler takes the raw
  `Request` and calls `await request.json()` inside a `try/except`, falling back to `{}` -- this
  matches the task's requirement that `/submit` accept *either* an empty body (submit-all) or
  `{"transaction_ids": [...]}` (submit-subset) without over-constraining the schema.

Sources:
- [Static Files - StaticFiles - FastAPI](https://fastapi.tiangolo.com/reference/staticfiles/)
- [How can I serve static files (html, js) easily? · fastapi/fastapi Discussion #8259](https://github.com/fastapi/fastapi/discussions/8259)
- [How to Implement Background Tasks in FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-background-tasks/view)

## Query: pytest coverage of `if __name__ == "__main__": raise SystemExit(main())` guards, and
   monkeypatching `Path.unlink` to simulate a filesystem error in a `_process_queue` cleanup path
- Search: pytest runpy.run_module cover if __name__ == "__main__" guard coverage.py 2026; pytest
  monkeypatch.setattr Path.unlink simulate OSError best practice
- context7 MCP tool was not available in this session's toolset (no `mcp.json` entry configured for
  it); intended target library IDs are `/pytest-dev/pytest` (monkeypatch how-to) and
  `/nedbat/coveragepy` (coverage.py exclude-lines / subprocess-coverage docs). Backed up with a live
  web search (see Sources below) confirming current (2026) guidance.
- Applied: (1) Rather than excluding each agent's `if __name__ == "__main__": raise
  SystemExit(main())` line via a `# pragma: no cover` / `coverage.py` `exclude_lines` config entry
  (the commonly documented workaround when a module is only ever *imported* by tests), this test
  suite instead exercises those two lines for real using `runpy.run_module("agents.<mod>",
  run_name="__main__")` after `monkeypatch.setattr(sys, "argv", [...])`, wrapped in `pytest.raises
  (SystemExit)` and asserting `exc_info.value.code == 0` -- `runpy.run_module` re-executes the
  module's top-level code in the *same* process (unlike a `subprocess.run` invocation, whose
  coverage would not be collected by the parent process's `coverage.py` run), so the dunder-main
  guard is measured as covered without any coverage-config exclusions or `COVERAGE_PROCESS_START`
  subprocess-coverage plumbing, for `agents/transaction_validator.py`,
  `agents/fraud_detector.py`, and `agents/compliance_checker.py`. (2) For the defensive
  `except OSError: pass` best-effort cleanup branches inside each agent's `_process_queue()` (the
  `path.unlink()` / `moved_path.unlink()` calls), applied the documented
  `monkeypatch.setattr(pathlib.Path, "unlink", fake_unlink)` pattern -- patching the *class*
  attribute (not a single instance) so every `Path` object touched during that test raises
  `OSError`, letting the test assert the batch still completes (`processed == 1`) rather than
  crashing, without needing real filesystem permission tricks (which are unreliable/non-portable
  across the Windows test environment this suite runs in).

Sources:
- [Why can't coverage the data in the "if __name__ == "__main__":" · Issue #552 · pytest-dev/pytest-cov](https://github.com/pytest-dev/pytest-cov/issues/552)
- [`__name__ == '__main__'` block reported as not covered even though it's executing · Issue #651 · pytest-dev/pytest-cov](https://github.com/pytest-dev/pytest-cov/issues/651)
- [How to monkeypatch/mock modules and environments - pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- [The Ultimate Guide To Using Pytest Monkeypatch with Real Code Examples | Pytest with Eric](https://pytest-with-eric.com/mocking/pytest-monkeypatch/)
