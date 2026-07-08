"""Shared message-protocol helper for the banking transaction-processing pipeline.

This module is the single, stable piece of glue every pipeline agent depends on. It provides:

* The standard JSON message shape (``message_id``, ``timestamp``, ``source_agent``,
  ``target_agent``, ``message_type``, ``data``) required by ``TASKS.md`` Task 2.
* Read / write / **atomic** move helpers for passing messages between the file-based
  ``shared/{input,processing,output,results}/`` queues. Writes are atomic (write-to-temp then
  ``os.replace``) and idempotent/deterministic for duplicate ``transaction_id`` values.
* ``decimal.Decimal`` money parsing and ISO 4217 currency validation / minor-unit quantization
  (``ROUND_HALF_EVEN``) -- **never** ``float``.
* ISO 8601 UTC audit logging (timestamp, agent name, transaction id, outcome) with PII masking:
  account numbers are masked to the last 4 digits and ``name``-type fields are never logged.

The shared/ and logs/ roots are resolved from environment variables so that tests can inject an
isolated filesystem (e.g. ``tmp_path``) without touching the project's real tree:

* ``PIPELINE_SHARED_ROOT`` -> defaults to ``<repo>/shared``
* ``PIPELINE_LOGS_DIR``    -> defaults to ``<repo>/logs``
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Roots & directory layout
# ---------------------------------------------------------------------------

SHARED_SUBDIRS: tuple[str, ...] = ("input", "processing", "output", "results")

AGENT_NAMES: frozenset[str] = frozenset(
    {"transaction_validator", "fraud_detector", "compliance_checker", "integrator"}
)


def get_repo_root() -> Path:
    """Return the ``homework-6`` project root (the parent of the ``agents`` package)."""
    return Path(__file__).resolve().parent.parent


def get_shared_root() -> Path:
    """Resolve the ``shared/`` root, honouring ``PIPELINE_SHARED_ROOT`` for test isolation."""
    override = os.environ.get("PIPELINE_SHARED_ROOT")
    if override:
        return Path(override).resolve()
    return get_repo_root() / "shared"


def get_logs_dir() -> Path:
    """Resolve the ``logs/`` directory, honouring ``PIPELINE_LOGS_DIR`` for test isolation."""
    override = os.environ.get("PIPELINE_LOGS_DIR")
    if override:
        return Path(override).resolve()
    return get_repo_root() / "logs"


def shared_subdir(name: str) -> Path:
    """Return the path to one of the ``shared/`` sub-queues (``input``/``processing``/...)."""
    if name not in SHARED_SUBDIRS:
        raise ValueError(f"unknown shared subdir: {name!r}")
    return get_shared_root() / name


def ensure_dirs() -> dict[str, Path]:
    """Create the ``shared/`` tree (and ``logs/``) if absent; return the sub-queue paths."""
    root = get_shared_root()
    paths: dict[str, Path] = {}
    for name in SHARED_SUBDIRS:
        p = root / name
        p.mkdir(parents=True, exist_ok=True)
        paths[name] = p
    get_logs_dir().mkdir(parents=True, exist_ok=True)
    return paths


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def iso_now() -> str:
    """Current UTC time as an ISO 8601 string with a trailing ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_timestamp(raw: str) -> datetime:
    """Parse an ISO 8601 timestamp (accepting a trailing ``Z``) into an aware UTC datetime."""
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Standard message shape
# ---------------------------------------------------------------------------


def new_message_id() -> str:
    return str(uuid.uuid4())


def build_message(
    data: dict[str, Any],
    *,
    source_agent: str,
    target_agent: str,
    message_type: str = "transaction",
    message_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Wrap ``data`` in the standard pipeline message envelope."""
    return {
        "message_id": message_id or new_message_id(),
        "timestamp": timestamp or iso_now(),
        "source_agent": source_agent,
        "target_agent": target_agent,
        "message_type": message_type,
        "data": data,
    }


def transaction_id_of(message: dict[str, Any]) -> str:
    """Extract the ``transaction_id`` from a message's ``data`` payload."""
    data = message.get("data") or {}
    return str(data.get("transaction_id", "")).strip()


# ---------------------------------------------------------------------------
# Atomic JSON file I/O
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, obj: Any, *, attempts: int = 3) -> Path:
    """Atomically write ``obj`` as JSON to ``path`` (temp file in same dir + ``os.replace``).

    Retries up to ``attempts`` times to tolerate transient disk/permission errors (edge case 10).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, indent=2, sort_keys=True, default=str)
    last_err: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=str(path.parent), prefix=f".{path.stem}.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_name, path)
                return path
            finally:
                if os.path.exists(tmp_name):
                    try:
                        os.remove(tmp_name)
                    except OSError:
                        pass
        except OSError as exc:  # pragma: no cover - exercised via simulated failures
            last_err = exc
    raise OSError(f"failed to write {path} after {attempts} attempts: {last_err}")


def read_message(path: str | Path) -> dict[str, Any]:
    """Read a JSON message file. Raises ``ValueError`` on malformed JSON (fail-closed callers)."""
    p = Path(path)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed_input: {p.name}: {exc}") from exc


def list_messages(subdir: str) -> list[Path]:
    """List message JSON files in a shared sub-queue (ignores temp/hidden files)."""
    d = shared_subdir(subdir)
    if not d.exists():
        return []
    return sorted(
        p for p in d.glob("*.json") if not p.name.startswith(".")
    )


def write_message(
    message: dict[str, Any], subdir: str, *, filename: str | None = None
) -> Path:
    """Atomically write ``message`` into a shared sub-queue, keyed by ``transaction_id`` by default."""
    txn_id = transaction_id_of(message) or message.get("message_id") or new_message_id()
    name = filename or f"{_safe_name(txn_id)}.json"
    return _atomic_write_json(shared_subdir(subdir) / name, message)


def move_message(
    src: str | Path, subdir: str, *, filename: str | None = None
) -> Path:
    """Move a message file from ``src`` into a shared sub-queue atomically, then remove the source."""
    src = Path(src)
    message = read_message(src)
    dest = write_message(message, subdir, filename=filename)
    try:
        src.unlink()
    except OSError:
        pass
    return dest


def _safe_name(txn_id: str) -> str:
    """Sanitise a transaction id for use as a filename."""
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(txn_id)) or "unknown"


# ---------------------------------------------------------------------------
# Results & idempotency
# ---------------------------------------------------------------------------


def result_path(transaction_id: str) -> Path:
    return shared_subdir("results") / f"{_safe_name(transaction_id)}.json"


def result_exists(transaction_id: str) -> bool:
    return result_path(transaction_id).exists()


def read_result(transaction_id: str) -> dict[str, Any] | None:
    p = result_path(transaction_id)
    if not p.exists():
        return None
    try:
        return read_message(p)
    except ValueError:
        return None


def write_result(message: dict[str, Any]) -> Path:
    """Atomically write a terminal-outcome message to ``shared/results/<transaction_id>.json``."""
    txn_id = transaction_id_of(message) or message.get("message_id") or new_message_id()
    return _atomic_write_json(result_path(txn_id), message)


# ---------------------------------------------------------------------------
# Money: decimal parsing, ISO 4217 currency, quantization
# ---------------------------------------------------------------------------

# ISO 4217 minor-unit exponents (decimal places). Named constant, not inline magic numbers.
CURRENCY_MINOR_UNITS: dict[str, int] = {
    "USD": 2, "EUR": 2, "GBP": 2, "CHF": 2, "CAD": 2, "AUD": 2, "NZD": 2,
    "CNY": 2, "HKD": 2, "SGD": 2, "SEK": 2, "NOK": 2, "DKK": 2, "PLN": 2,
    "MXN": 2, "BRL": 2, "ZAR": 2, "INR": 2, "RUB": 2, "TRY": 2, "AED": 2,
    "SAR": 2, "ILS": 2, "THB": 2, "UAH": 2,
    "JPY": 0, "KRW": 0, "ISK": 0, "HUF": 2,  # HUF minor unit is 2 per ISO 4217
    "BHD": 3, "KWD": 3, "OMR": 3, "TND": 3,
}

# The set of currencies this pipeline accepts as valid ISO 4217 alphabetic codes.
ISO_4217_CURRENCIES: frozenset[str] = frozenset(CURRENCY_MINOR_UNITS)

DEFAULT_MINOR_UNITS = 2


def is_valid_currency(code: Any) -> bool:
    return isinstance(code, str) and code.upper() in ISO_4217_CURRENCIES


def minor_units(currency: str) -> int:
    return CURRENCY_MINOR_UNITS.get(str(currency).upper(), DEFAULT_MINOR_UNITS)


def to_decimal(raw: Any) -> Decimal:
    """Parse ``raw`` into a finite ``Decimal``. Raises ``ValueError`` on any malformed value."""
    if isinstance(raw, float):
        # Guard against float imprecision entering the pipeline.
        raw = repr(raw)
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid_amount:{raw!r}") from exc
    if not value.is_finite():
        raise ValueError(f"invalid_amount:{raw!r}")
    return value


def quantize_amount(value: Decimal, currency: str) -> Decimal:
    """Quantize ``value`` to the currency's ISO 4217 minor unit using ``ROUND_HALF_EVEN``."""
    exp = minor_units(currency)
    quantum = Decimal(1).scaleb(-exp) if exp else Decimal(1)
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


def parse_amount(raw: Any, currency: str) -> Decimal:
    """Parse and quantize a monetary amount for the given currency (keeps sign)."""
    return quantize_amount(to_decimal(raw), currency)


def format_amount(value: Decimal) -> str:
    return str(value)


# ---------------------------------------------------------------------------
# PII masking & audit logging
# ---------------------------------------------------------------------------

# Field names that must never be logged in plaintext.
_NAME_LIKE_FIELDS = frozenset({"name", "full_name", "account_holder", "holder_name", "customer_name"})
_ACCOUNT_LIKE_FIELDS = frozenset({"source_account", "destination_account", "account", "account_number"})


def mask_account(account: Any) -> str:
    """Mask an account number to the last 4 digits, e.g. ``ACC-1001`` -> ``ACC-***1001``.

    Only the final 4 alphanumeric characters remain visible; everything else is redacted.
    """
    if account is None:
        return ""
    text = str(account)
    tail = text[-4:] if len(text) >= 4 else text
    return f"ACC-***{tail}"


def mask_pii(obj: Any) -> Any:
    """Recursively mask account numbers and drop name-like fields for safe logging."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, val in obj.items():
            lkey = str(key).lower()
            if lkey in _NAME_LIKE_FIELDS:
                cleaned[key] = "***REDACTED***"
            elif lkey in _ACCOUNT_LIKE_FIELDS:
                cleaned[key] = mask_account(val)
            else:
                cleaned[key] = mask_pii(val)
        return cleaned
    if isinstance(obj, (list, tuple)):
        return [mask_pii(v) for v in obj]
    return obj


def audit_log(
    agent_name: str,
    transaction_id: str,
    outcome: str,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one ISO 8601 audit entry to ``logs/audit.log`` (append-only, PII-masked).

    The entry is a single JSON object per line: ``{timestamp, agent_name, transaction_id,
    outcome, ...extra}``. Any account/name fields in ``extra`` are masked before writing.
    Returns the entry dict (also useful for tests). Never raises on primary-log failure; a
    best-effort fallback line is written to ``logs/audit_error.log`` instead.
    """
    entry: dict[str, Any] = {
        "timestamp": iso_now(),
        "agent_name": agent_name,
        "transaction_id": str(transaction_id),
        "outcome": outcome,
    }
    if extra:
        entry.update(mask_pii(dict(extra)))

    line = json.dumps(entry, default=str) + "\n"
    logs_dir = get_logs_dir()
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        with open(logs_dir / "audit.log", "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:  # pragma: no cover - best-effort fallback path
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            with open(logs_dir / "audit_error.log", "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass
    return entry


__all__ = [
    "SHARED_SUBDIRS",
    "AGENT_NAMES",
    "get_repo_root",
    "get_shared_root",
    "get_logs_dir",
    "shared_subdir",
    "ensure_dirs",
    "iso_now",
    "parse_timestamp",
    "new_message_id",
    "build_message",
    "transaction_id_of",
    "read_message",
    "list_messages",
    "write_message",
    "move_message",
    "result_path",
    "result_exists",
    "read_result",
    "write_result",
    "CURRENCY_MINOR_UNITS",
    "ISO_4217_CURRENCIES",
    "is_valid_currency",
    "minor_units",
    "to_decimal",
    "quantize_amount",
    "parse_amount",
    "format_amount",
    "mask_account",
    "mask_pii",
    "audit_log",
]
