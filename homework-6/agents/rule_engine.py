"""Rule Engine / Pipeline Orchestrator agent for the banking pipeline (serves M6).

Implements ``determine_pipeline_order(requested_order: list[str] | None = None) -> list[str]`` per
``specification.md`` (Task: Rule Engine / Pipeline Orchestrator). This agent does not score or
decide anything about a transaction; it decides the **execution order** of the other three agents
(``transaction_validator``, ``fraud_detector``, ``compliance_checker``) for a given run.

Resolution order:

1. If the caller explicitly supplies ``requested_order`` (a REST request's ``pipeline_order`` field,
   a batch record's own ``pipeline_order`` field, or a direct integrator call), it is validated as a
   permutation of exactly the three required agent names and, if valid, returned verbatim.
2. Otherwise the project-wide ``default_order`` is loaded from
   ``agents/config/pipeline_rules.json`` (falling back to the hardcoded
   ``transaction_validator -> fraud_detector -> compliance_checker`` order if the file/key is
   absent).

There is no hardcoded assumption that validation must run first -- that is only the default, not a
rule. An invalid ``requested_order`` (wrong length, duplicate, or unknown agent name) fails closed to
``default_order`` and is audit-logged as ``invalid_pipeline_order_fallback`` so the rejected input is
traceable.

This module reuses ``agents.protocol`` for audit logging -- it performs no file I/O of its own
beyond the one-time config load at import time, mirroring ``agents.fraud_detector``'s
``load_rules``/``RULES`` pattern.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Sequence

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agents import protocol

AGENT_NAME = "rule_engine"

_CONFIG_PATH = protocol.get_repo_root() / "agents" / "config" / "pipeline_rules.json"

# The fixed set of pipeline agents a valid order must contain -- exactly once each, no more, no
# fewer. Named constant, not an inline literal scattered through the validation logic.
PIPELINE_AGENTS: frozenset[str] = frozenset(
    {"transaction_validator", "fraud_detector", "compliance_checker"}
)

# Hardcoded fallback used only when agents/config/pipeline_rules.json is absent or malformed.
_HARDCODED_DEFAULT_ORDER: tuple[str, ...] = (
    "transaction_validator",
    "fraud_detector",
    "compliance_checker",
)


def is_valid_order(order: Any) -> bool:
    """True if ``order`` is a permutation of exactly ``PIPELINE_AGENTS`` -- no more, no fewer."""
    if not isinstance(order, Sequence) or isinstance(order, (str, bytes)):
        return False
    if len(order) != len(PIPELINE_AGENTS):
        return False
    if len(set(order)) != len(order):
        return False  # no duplicates
    return set(order) == PIPELINE_AGENTS


def load_default_order(path: pathlib.Path | str | None = None) -> list[str]:
    """Load ``default_order`` from ``agents/config/pipeline_rules.json``.

    Falls back to the hardcoded default order (validator -> fraud -> compliance) if the file is
    absent, malformed, or its ``default_order`` is not itself a valid permutation of the three
    required agent names -- this loader must never raise and must never return an invalid order.
    """
    cfg_path = pathlib.Path(path) if path else _CONFIG_PATH
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        order = [str(a) for a in raw["default_order"]]
    except (OSError, ValueError, KeyError, TypeError):
        return list(_HARDCODED_DEFAULT_ORDER)

    if not is_valid_order(order):
        return list(_HARDCODED_DEFAULT_ORDER)
    return order


# Loaded once at import time; ``load_default_order()`` remains available for tests that want to
# exercise an alternate/synthetic config file.
DEFAULT_ORDER: list[str] = load_default_order()


def determine_pipeline_order(
    requested_order: list[str] | None = None,
    *,
    transaction_id: str | None = None,
) -> list[str]:
    """Resolve the execution order of the three pipeline agents for one transaction/run.

    Caller-specified order always takes precedence over the config-file default; the config-file
    default always takes precedence over the hardcoded fallback (see :func:`load_default_order`).
    ``transaction_id`` is optional and used only to make an ``invalid_pipeline_order_fallback``
    audit line traceable to the transaction that requested the bad order; it is not part of the
    resolution logic itself.
    """
    if requested_order is not None:
        if is_valid_order(requested_order):
            return list(requested_order)
        protocol.audit_log(
            AGENT_NAME,
            transaction_id or "-",
            "invalid_pipeline_order_fallback",
            extra={"requested_order": requested_order, "fallback_order": DEFAULT_ORDER},
        )
        return list(DEFAULT_ORDER)

    return list(DEFAULT_ORDER)


__all__ = [
    "AGENT_NAME",
    "PIPELINE_AGENTS",
    "DEFAULT_ORDER",
    "load_default_order",
    "is_valid_order",
    "determine_pipeline_order",
]
