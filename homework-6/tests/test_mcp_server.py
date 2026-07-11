"""Unit tests for the custom FastMCP server helpers (TASKS.md Task 4).

Exercises the plain, transport-free helpers behind the MCP tools/resource
(``_status_for``, ``_all_results``, ``_summary_text``) against an isolated ``shared/`` tree so no
test ever touches the project's real results. The MCP server module is loaded by file path because
the ``mcp/`` directory is intentionally not a Python package (it must not shadow the installed
``mcp`` SDK); see ``mcp/server.py``.
"""

from __future__ import annotations

import importlib.util
import json
import sys as _sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_sys.path.insert(0, str(_REPO_ROOT))

from agents import protocol  # noqa: E402


def _load_server_module():
    """Load ``mcp/server.py`` by path (the dir is deliberately not an importable package)."""
    spec = importlib.util.spec_from_file_location(
        "mcp_pipeline_server", _REPO_ROOT / "mcp" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server_module()


@pytest.fixture(autouse=True)
def isolated_shared(tmp_path, monkeypatch):
    """Point the shared protocol at an isolated tmp_path filesystem for every test."""
    monkeypatch.setenv("PIPELINE_SHARED_ROOT", str(tmp_path / "shared"))
    monkeypatch.setenv("PIPELINE_LOGS_DIR", str(tmp_path / "logs"))
    protocol.ensure_dirs()
    yield


def _write_result(transaction_id: str, data_overrides: dict) -> None:
    message = protocol.build_message(
        {"transaction_id": transaction_id, **data_overrides},
        source_agent="compliance_checker",
        target_agent="integrator",
        message_type="result",
    )
    protocol.write_result(message)


def test_status_for_found_returns_pii_safe_view():
    _write_result(
        "TXN001",
        {
            "status": "cleared",
            "decision": "cleared",
            "reason": [],
            "risk_score": 0,
            "currency": "USD",
            # PII that must NOT be surfaced over MCP:
            "source_account": "ACC-1001",
            "destination_account": "ACC-2001",
            "description": "Monthly rent payment",
        },
    )
    view = server._status_for("TXN001")
    assert view["found"] is True
    assert view["transaction_id"] == "TXN001"
    assert view["decision"] == "cleared"
    # Sensitive fields are omitted.
    assert "source_account" not in view
    assert "destination_account" not in view
    assert "description" not in view


def test_status_for_missing_returns_not_found():
    view = server._status_for("DOES-NOT-EXIST")
    assert view == {"transaction_id": "DOES-NOT-EXIST", "found": False}


def test_status_for_blank_id_is_not_found():
    view = server._status_for("   ")
    assert view["found"] is False


def test_all_results_aggregates_counts_and_sorts():
    _write_result("TXN002", {"status": "flagged", "decision": "flagged"})
    _write_result("TXN001", {"status": "cleared", "decision": "cleared"})
    _write_result("TXN003", {"status": "cleared", "decision": "cleared"})

    result = server._all_results()
    assert result["total"] == 3
    assert result["by_decision"] == {"cleared": 2, "flagged": 1}
    assert result["by_status"] == {"cleared": 2, "flagged": 1}
    ids = [t["transaction_id"] for t in result["transactions"]]
    assert ids == ["TXN001", "TXN002", "TXN003"]


def test_all_results_skips_summary_and_malformed(tmp_path):
    _write_result("TXN001", {"status": "cleared", "decision": "cleared"})
    results_dir = protocol.shared_subdir("results")
    # summary.json must be ignored, and a malformed file must be skipped (not raise).
    (results_dir / "summary.json").write_text("{}", encoding="utf-8")
    (results_dir / "TXNBAD.json").write_text("{ not json", encoding="utf-8")

    result = server._all_results()
    assert result["total"] == 1
    assert result["transactions"][0]["transaction_id"] == "TXN001"


def test_summary_text_reads_summary_json_when_present():
    summary = {"total": 2, "cleared": 2, "flagged": 0}
    (protocol.shared_subdir("results") / "summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    text = server._summary_text()
    assert '"total": 2' in text
    assert "not found" not in text


def test_summary_text_falls_back_when_missing():
    _write_result("TXN001", {"status": "cleared", "decision": "cleared"})
    text = server._summary_text()
    assert "summary.json not found" in text
    assert "TXN001" in text
