"""FastAPI frontend for the banking transaction-processing pipeline (serves M5).

This module is a **read-only observer plus an injector**. It never implements or duplicates
validator / fraud-scoring / compliance logic:

* ``POST /submit`` and ``POST /random`` build standard-shape messages using the *exact same*
  ``agents.protocol.build_message`` construction that ``integrator.py`` uses, and then drive each
  one through the real pipeline by calling the real agents' ``process_message`` functions
  (``transaction_validator`` -> ``fraud_detector`` -> ``compliance_checker``, in order) -- the same
  code path ``integrator.process_transaction`` uses, not a reimplementation. The only thing added
  here is a deliberate **1-5s pause between stages** and an in-memory live tracker so the dashboard
  can animate each transaction moving through the pipeline in real time.
* ``GET /api/status`` reads pipeline state from ``shared/{input,processing,output,results}/`` and
  overlays the in-memory live tracker (which stage each in-flight transaction is currently in). It
  never calls any agent's scoring/decision logic itself.
* ``POST /clear`` wipes the ``shared/`` queues + results and the live tracker so the demo can start
  fresh.
* Every response is scrubbed through ``agents.protocol.mask_pii`` / ``mask_account`` so no unmasked
  account number (and no name-type field) ever leaves this process.

Run with:  ``python -m uvicorn frontend.server:app --reload``  (``uvicorn`` may not be on PATH as a
standalone command; the ``python -m`` form always works.)
"""

from __future__ import annotations

import sys
import pathlib

# Make sure the homework-6 project root is importable (``agents``, ``integrator``) regardless of
# the working directory uvicorn is started from, and make the Python-3.14rc compat shim apply
# BEFORE fastapi/pydantic are ever imported.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from frontend import _py314_compat  # noqa: F401,E402  (patches typing before fastapi import)

import asyncio  # noqa: E402
import random  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime, timezone, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import Any  # noqa: E402

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from agents import protocol  # noqa: E402
from agents import transaction_validator, fraud_detector, compliance_checker  # noqa: E402
import integrator  # noqa: E402

APP_DIR = pathlib.Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
SAMPLE_FILE = protocol.get_repo_root() / "sample-transactions.json"

FRONTEND_AGENT_NAME = "frontend"

# Simulated per-stage processing delay (seconds). Each transaction pauses a random amount in this
# range between every pipeline stage so the dashboard can show the lifecycle advancing in real time.
DEFAULT_MIN_DELAY = 1.0
DEFAULT_MAX_DELAY = 5.0

app = FastAPI(title="Banking Pipeline Dashboard")

# Serve any future static assets (css/js) under /static in addition to the single index.html at
# GET / below.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# In-memory live tracker
# ---------------------------------------------------------------------------
#
# ``LIVE`` holds one prebuilt status entry per in-flight (or recently finished) transaction, keyed
# by transaction_id. It is the animation layer: it records which stage a transaction is *currently*
# in, including the transient "scoring"/"compliance" stages that never sit still on disk. The real
# terminal outcome is always the one the agents wrote to ``shared/results/``; LIVE just narrates the
# journey there. ``ANIM_TASKS`` tracks the background asyncio tasks so ``/clear`` can cancel them.

LIVE: dict[str, dict[str, Any]] = {}
ANIM_TASKS: set[asyncio.Task] = set()

# Canonical ordered pipeline stages (mirrored in the frontend for the stepper).
STAGE_RECEIVED = "received"
STAGE_VALIDATING = "processing"
STAGE_VALIDATED = "validated"
STAGE_SCORING = "scoring"
STAGE_SCORED = "scored"
STAGE_COMPLIANCE = "compliance"
STAGE_RESULTS = "results"


def _reason_list(reason: Any) -> list[str]:
    if isinstance(reason, list):
        return [str(r) for r in reason]
    if reason:
        return [str(reason)]
    return []


def _entry(txn_id: str, stage: str, data: dict[str, Any], *, last_updated: str) -> dict[str, Any]:
    """Build one status entry (PII-masked) for the dashboard, shared by the live and file views."""
    data = data or {}
    masked = protocol.mask_pii(data)  # recursively masks account numbers; drops name-like fields

    status = data.get("status")
    decision = data.get("decision")
    terminal = stage == STAGE_RESULTS
    # Validation-rejected transactions never acquire a `decision` field (they bypass fraud/
    # compliance entirely), so fall back to `status` (e.g. "rejected") for the terminal outcome.
    outcome = (decision or status) if terminal else "in_progress"

    return {
        "transaction_id": txn_id,
        "stage": stage,
        "status": status,
        "decision": decision,
        "outcome": outcome,
        "reason": _reason_list(data.get("reason")),
        "risk_score": data.get("risk_score"),
        "fraud_review": data.get("fraud_review"),
        "fraud_signals": data.get("fraud_signals"),
        "requires_report": data.get("requires_report"),
        "amount": data.get("amount"),
        "currency": data.get("currency"),
        "transaction_type": data.get("transaction_type"),
        "source_account": masked.get("source_account"),
        "destination_account": masked.get("destination_account"),
        "last_updated": last_updated,
    }


def _set_live(txn_id: str, message: dict[str, Any], stage: str) -> None:
    """Record the current stage of an in-flight transaction in the live tracker."""
    data = message.get("data") if isinstance(message, dict) else {}
    LIVE[txn_id] = _entry(txn_id, stage, data or {}, last_updated=protocol.iso_now())


# ---------------------------------------------------------------------------
# Shared-queue reset helpers
# ---------------------------------------------------------------------------


def _reset_transaction(txn_id: str) -> None:
    """Remove any prior queue/result files for ``txn_id`` so it re-processes from a clean slate.

    Without this, the agents' idempotency guard (``result_exists``) would short-circuit a
    re-submitted transaction and the animation would have nothing to show.
    """
    safe = protocol._safe_name(txn_id)
    for sub in protocol.SHARED_SUBDIRS:
        p = protocol.shared_subdir(sub) / f"{safe}.json"
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def _clear_shared() -> int:
    """Delete every message/result file in ``shared/`` and clear the live tracker. Returns count."""
    protocol.ensure_dirs()
    removed = 0
    for sub in protocol.SHARED_SUBDIRS:
        d = protocol.shared_subdir(sub)
        for pattern in ("*.json", ".*"):
            for p in d.glob(pattern):
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    pass
    LIVE.clear()
    return removed


# ---------------------------------------------------------------------------
# Animated per-transaction driver (real agents + 1-5s pauses between stages)
# ---------------------------------------------------------------------------


async def _pause(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def _animate(record: dict[str, Any], lo: float, hi: float) -> None:
    """Drive one transaction through validator -> fraud -> compliance with a pause between stages.

    Calls the real agents' ``process_message`` (via ``asyncio.to_thread`` since they do blocking
    file I/O) -- no scoring/decision logic is reimplemented here. Between each stage it updates the
    live tracker and sleeps a random 1-5s so the dashboard animates the journey.
    """
    txn_id = str(record.get("transaction_id") or "").strip() or f"UNKNOWN-{uuid.uuid4().hex[:6]}"
    try:
        _reset_transaction(txn_id)

        message = protocol.build_message(
            dict(record),
            source_agent=FRONTEND_AGENT_NAME,
            target_agent="transaction_validator",
            message_type="transaction",
        )
        protocol.write_message(message, "input")
        _set_live(txn_id, message, STAGE_RECEIVED)
        await _pause(lo, hi)

        # Stage: validating.
        _set_live(txn_id, message, STAGE_VALIDATING)
        await _pause(lo, hi)
        validated = await asyncio.to_thread(transaction_validator.process_message, message)
        vdata = validated.get("data") or {}
        if vdata.get("status") != "validated":
            # Rejected (or errored) at validation -- terminal, bypasses fraud/compliance.
            _set_live(txn_id, validated, STAGE_RESULTS)
            return
        _set_live(txn_id, validated, STAGE_VALIDATED)
        await _pause(lo, hi)

        # Stage: fraud scoring.
        _set_live(txn_id, validated, STAGE_SCORING)
        await _pause(lo, hi)
        scored = await asyncio.to_thread(fraud_detector.process_message, validated)
        _set_live(txn_id, scored, STAGE_SCORED)
        await _pause(lo, hi)

        # Stage: compliance screening.
        _set_live(txn_id, scored, STAGE_COMPLIANCE)
        await _pause(lo, hi)
        final = await asyncio.to_thread(compliance_checker.process_message, scored)
        _set_live(txn_id, final, STAGE_RESULTS)
    except asyncio.CancelledError:  # /clear cancelled us mid-flight -- stop quietly.
        raise
    except Exception as exc:  # fail-closed: never let one bad record crash the loop.
        protocol.audit_log(
            FRONTEND_AGENT_NAME, txn_id, "error", extra={"error_type": type(exc).__name__}
        )


def _schedule(records: list[dict[str, Any]], lo: float, hi: float) -> None:
    """Launch one background animation task per record (they run concurrently)."""
    for record in records:
        task = asyncio.create_task(_animate(record, lo, hi))
        ANIM_TASKS.add(task)
        task.add_done_callback(ANIM_TASKS.discard)


def _delays_from_body(body: Any) -> tuple[float, float]:
    lo, hi = DEFAULT_MIN_DELAY, DEFAULT_MAX_DELAY
    if isinstance(body, dict):
        try:
            if body.get("min_delay") is not None:
                lo = max(0.0, float(body["min_delay"]))
            if body.get("max_delay") is not None:
                hi = max(lo, float(body["max_delay"]))
        except (TypeError, ValueError):
            pass
    return lo, hi


# ---------------------------------------------------------------------------
# Random transaction generation
# ---------------------------------------------------------------------------

_VALID_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]
_HOME_COUNTRIES = ["US"]
_FOREIGN_COUNTRIES = ["DE", "GB", "FR", "JP", "SG", "AE", "BR", "ZA"]
_CHANNELS = ["online", "branch", "api", "mobile"]
_TYPES = ["transfer", "wire_transfer", "refund"]
_DESCRIPTIONS = [
    "Invoice settlement", "Monthly rent", "Consulting fee", "Equipment purchase",
    "Salary advance", "Vendor payment", "Property settlement", "Order refund",
]


def _generate_random_record() -> dict[str, Any]:
    """Build a random but schema-valid transaction, tuned to exercise varied pipeline outcomes.

    ~10% of the time it emits an invalid ISO 4217 currency so the dashboard also shows a
    validation rejection; amounts and timestamps are spread so cleared / flagged / requires-report
    / cross-border / off-hours cases all appear over repeated clicks.
    """
    txn_id = f"RND-{uuid.uuid4().hex[:6].upper()}"

    # Amount band: mostly ordinary, sometimes high-value (>= reporting/high-value threshold).
    band = random.random()
    if band < 0.55:
        amount = Decimal(random.randint(50, 4999)) + Decimal(random.randint(0, 99)) / 100
    elif band < 0.8:
        amount = Decimal(random.randint(5000, 14999)) + Decimal(random.randint(0, 99)) / 100
    else:
        amount = Decimal(random.randint(15000, 90000)) + Decimal(random.randint(0, 99)) / 100

    txn_type = random.choice(_TYPES)
    if txn_type == "refund":
        amount = -amount  # validator accepts a negative amount only for refunds.

    currency = random.choice(_VALID_CURRENCIES)
    if random.random() < 0.10:
        currency = "XYZ"  # invalid ISO 4217 -> rejected at validation.

    # ~40% cross-border to exercise the fraud + compliance cross-border rules.
    country = random.choice(_FOREIGN_COUNTRIES) if random.random() < 0.4 else random.choice(_HOME_COUNTRIES)

    # Random time-of-day so some land in the off-hours window.
    ts = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(
        hours=random.randint(0, 23), minutes=random.randint(0, 59)
    )

    return {
        "transaction_id": txn_id,
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_account": f"ACC-{random.randint(1000, 1999)}",
        "destination_account": f"ACC-{random.randint(2000, 9999)}",
        "amount": f"{amount:.2f}",
        "currency": currency,
        "transaction_type": txn_type,
        "description": random.choice(_DESCRIPTIONS),
        "metadata": {"channel": random.choice(_CHANNELS), "country": country},
    }


# ---------------------------------------------------------------------------
# GET /  -- serve the static dashboard page
# ---------------------------------------------------------------------------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


# ---------------------------------------------------------------------------
# POST /submit -- inject sample transactions and animate them through the pipeline
# ---------------------------------------------------------------------------


@app.post("/submit")
async def submit(request: Request) -> dict[str, Any]:
    """Drop selected (or all) sample transactions into the pipeline and animate them.

    Optional JSON body: ``{"transaction_ids": [...], "min_delay": 1, "max_delay": 5}``. An
    empty/absent body submits every record in ``sample-transactions.json`` with the default 1-5s
    per-stage delay. Returns immediately; progress is observed via ``GET /api/status``.
    """
    protocol.ensure_dirs()
    try:
        body = await request.json()
    except Exception:
        body = {}

    wanted: set[str] | None = None
    if isinstance(body, dict):
        ids = body.get("transaction_ids")
        if isinstance(ids, list) and ids:
            wanted = {str(i) for i in ids}
    lo, hi = _delays_from_body(body)

    records, _malformed = integrator.load_records(SAMPLE_FILE)
    selected = [r for r in records if wanted is None or str(r.get("transaction_id")) in wanted]

    _schedule(selected, lo, hi)
    return {
        "submitted": len(selected),
        "transaction_ids": [str(r.get("transaction_id")) for r in selected],
    }


# ---------------------------------------------------------------------------
# POST /random -- generate random transaction(s) and animate them
# ---------------------------------------------------------------------------


@app.post("/random")
async def random_transaction(request: Request) -> dict[str, Any]:
    """Generate ``count`` (default 1) random transactions and drive them through the pipeline."""
    protocol.ensure_dirs()
    try:
        body = await request.json()
    except Exception:
        body = {}

    count = 1
    if isinstance(body, dict) and body.get("count") is not None:
        try:
            count = max(1, min(20, int(body["count"])))
        except (TypeError, ValueError):
            count = 1
    lo, hi = _delays_from_body(body)

    records = [_generate_random_record() for _ in range(count)]
    _schedule(records, lo, hi)
    # Return a PII-masked preview so the caller can see what was generated.
    preview = [protocol.mask_pii(r) for r in records]
    return {"submitted": len(records), "transactions": preview}


# ---------------------------------------------------------------------------
# POST /clear -- cancel in-flight work and wipe shared/ + the live tracker
# ---------------------------------------------------------------------------


@app.post("/clear")
async def clear() -> dict[str, Any]:
    """Stop any in-flight animations and clear ``shared/`` results/queues + the live tracker."""
    for task in list(ANIM_TASKS):
        task.cancel()
    # Let cancellations settle so their file writes don't race the wipe.
    await asyncio.sleep(0.05)
    removed = _clear_shared()
    return {"cleared": True, "files_removed": removed}


# ---------------------------------------------------------------------------
# GET /api/status -- read-only lifecycle view (shared/ files overlaid with LIVE)
# ---------------------------------------------------------------------------

# Stage read-priority for the on-disk view: a terminal result always wins, then an output-stage
# message (validated or scored), then a processing-stage copy, then the raw input message.
_STAGE_READ_ORDER: tuple[str, ...] = ("results", "output", "processing", "input")


def _mtime_iso(path: pathlib.Path) -> str:
    """File mtime as an ISO 8601 UTC timestamp (used as the 'last-updated' signal)."""
    try:
        ts = path.stat().st_mtime
    except OSError:
        return protocol.iso_now()
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _collect_stage_state() -> dict[str, tuple[str, dict[str, Any], pathlib.Path]]:
    """Return ``{transaction_id: (stage, message, path)}`` read only from ``shared/`` files."""
    state: dict[str, tuple[str, dict[str, Any], pathlib.Path]] = {}
    for subdir in reversed(_STAGE_READ_ORDER):
        for path in protocol.list_messages(subdir):
            if subdir == "results" and path.name == "summary.json":
                continue
            try:
                message = protocol.read_message(path)
            except ValueError:
                continue
            txn_id = protocol.transaction_id_of(message) or path.stem
            if subdir == "output":
                data = message.get("data") or {}
                stage = STAGE_SCORED if data.get("status") == "scored" else STAGE_VALIDATED
            elif subdir == "input":
                stage = STAGE_RECEIVED
            else:
                stage = subdir  # "processing" or "results"
            state[txn_id] = (stage, message, path)
    return state


@app.get("/api/status")
def api_status() -> list[dict[str, Any]]:
    """One JSON entry per ``transaction_id``: the on-disk view, overlaid with the live tracker."""
    protocol.ensure_dirs()

    entries: dict[str, dict[str, Any]] = {}
    for txn_id, (stage, message, path) in _collect_stage_state().items():
        entries[txn_id] = _entry(txn_id, stage, message.get("data") or {}, last_updated=_mtime_iso(path))

    # Overlay the live tracker: it knows the transient scoring/compliance stages the disk can't show,
    # and it is authoritative for in-flight transactions.
    for txn_id, live in LIVE.items():
        entries[txn_id] = live

    ordered = sorted(entries.values(), key=lambda e: e["transaction_id"])
    return ordered
