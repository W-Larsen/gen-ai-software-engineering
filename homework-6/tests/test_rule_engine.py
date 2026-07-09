"""Unit tests for agents/rule_engine.py (serves M6, specification.md "Rule Engine / Pipeline
Orchestrator" task).

Covers: the hardcoded 3-stage default when no requested_order and no config file override the
in-memory DEFAULT_ORDER; a config-file default_order override via load_default_order(path=...); an
explicit caller-supplied non-default order returned verbatim; and an invalid requested_order (wrong
length, unknown agent name, or missing a required agent) falling back to the default with an
invalid_pipeline_order_fallback audit entry. The filesystem is isolated per test via
PIPELINE_SHARED_ROOT/PIPELINE_LOGS_DIR env vars pointing at pytest's tmp_path, matching the pattern
used by tests/test_integrator.py.
"""

from __future__ import annotations

import json
import sys as _sys
from pathlib import Path

import pytest

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import protocol, rule_engine

HARDCODED_DEFAULT = ["transaction_validator", "fraud_detector", "compliance_checker"]


@pytest.fixture(autouse=True)
def isolated_shared(tmp_path, monkeypatch):
    """Point the shared protocol at an isolated tmp_path filesystem for every test."""
    monkeypatch.setenv("PIPELINE_SHARED_ROOT", str(tmp_path / "shared"))
    monkeypatch.setenv("PIPELINE_LOGS_DIR", str(tmp_path / "logs"))
    protocol.ensure_dirs()
    yield


def _audit_lines() -> list[dict]:
    log_path = protocol.get_logs_dir() / "audit.log"
    if not log_path.exists():
        return []
    lines = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            lines.append(json.loads(line))
    return lines


# ---------------------------------------------------------------------------
# load_default_order() -- pure, injectable config loader
# ---------------------------------------------------------------------------


def test_load_default_order_falls_back_to_hardcoded_when_file_absent(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    assert rule_engine.load_default_order(path=missing) == HARDCODED_DEFAULT


def test_load_default_order_reads_a_custom_config_file(tmp_path):
    custom = tmp_path / "pipeline_rules.json"
    custom.write_text(
        json.dumps({"default_order": ["compliance_checker", "transaction_validator", "fraud_detector"]}),
        encoding="utf-8",
    )
    assert rule_engine.load_default_order(path=custom) == [
        "compliance_checker",
        "transaction_validator",
        "fraud_detector",
    ]


def test_load_default_order_falls_back_when_config_order_is_invalid(tmp_path):
    custom = tmp_path / "pipeline_rules.json"
    custom.write_text(
        json.dumps({"default_order": ["transaction_validator", "fraud_detector"]}),  # missing one
        encoding="utf-8",
    )
    assert rule_engine.load_default_order(path=custom) == HARDCODED_DEFAULT


# ---------------------------------------------------------------------------
# is_valid_order()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "order,expected",
    [
        (["transaction_validator", "fraud_detector", "compliance_checker"], True),
        (["compliance_checker", "fraud_detector", "transaction_validator"], True),
        (["fraud_detector", "compliance_checker"], False),  # missing transaction_validator
        (["transaction_validator", "fraud_detector", "unknown_agent"], False),  # unknown name
        (["transaction_validator", "transaction_validator", "fraud_detector"], False),  # duplicate
        ("transaction_validator", False),  # a bare string, not a list
        (None, False),
    ],
)
def test_is_valid_order(order, expected):
    assert rule_engine.is_valid_order(order) is expected


# ---------------------------------------------------------------------------
# determine_pipeline_order()
# ---------------------------------------------------------------------------


def test_determine_pipeline_order_defaults_when_no_requested_order():
    assert rule_engine.determine_pipeline_order() == HARDCODED_DEFAULT
    assert rule_engine.determine_pipeline_order(None) == HARDCODED_DEFAULT


def test_determine_pipeline_order_honours_config_file_default_override(monkeypatch):
    custom_default = ["compliance_checker", "transaction_validator", "fraud_detector"]
    monkeypatch.setattr(rule_engine, "DEFAULT_ORDER", custom_default)
    assert rule_engine.determine_pipeline_order() == custom_default


def test_determine_pipeline_order_returns_valid_requested_order_verbatim():
    custom_order = ["compliance_checker", "fraud_detector", "transaction_validator"]
    assert rule_engine.determine_pipeline_order(requested_order=custom_order) == custom_order


def test_determine_pipeline_order_falls_back_and_audits_on_invalid_requested_order():
    invalid_order = ["fraud_detector", "compliance_checker"]  # missing transaction_validator

    result = rule_engine.determine_pipeline_order(
        requested_order=invalid_order, transaction_id="TXN-INVALID-ORDER"
    )

    assert result == HARDCODED_DEFAULT

    lines = _audit_lines()
    fallback_lines = [l for l in lines if l.get("outcome") == "invalid_pipeline_order_fallback"]
    assert len(fallback_lines) == 1
    entry = fallback_lines[0]
    assert entry["agent_name"] == "rule_engine"
    assert entry["transaction_id"] == "TXN-INVALID-ORDER"


def test_determine_pipeline_order_falls_back_on_unknown_agent_name():
    invalid_order = ["transaction_validator", "fraud_detector", "settlement_processor"]
    assert rule_engine.determine_pipeline_order(requested_order=invalid_order) == HARDCODED_DEFAULT


def test_determine_pipeline_order_falls_back_on_duplicate_agent_name():
    invalid_order = ["transaction_validator", "transaction_validator", "compliance_checker"]
    assert rule_engine.determine_pipeline_order(requested_order=invalid_order) == HARDCODED_DEFAULT
