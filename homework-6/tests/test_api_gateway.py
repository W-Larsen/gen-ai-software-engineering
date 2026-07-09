"""Integration tests for the REST API Gateway (serves M7, specification.md "REST API Gateway"
task).

Uses ``fastapi.testclient.TestClient`` against the real ``frontend.server.app`` -- no mocking of
the pipeline agents -- with the shared/logs filesystem isolated per test via
PIPELINE_SHARED_ROOT/PIPELINE_LOGS_DIR env vars pointing at pytest's tmp_path, matching the pattern
used by tests/test_integrator.py and tests/test_rule_engine.py.
"""

from __future__ import annotations

import re
import sys as _sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import protocol
from frontend import server as frontend_server

# Matches an unmasked ACC-<digits> account number (i.e. NOT the ACC-***#### masked form).
_UNMASKED_ACCOUNT_PATTERN = re.compile(r"ACC-(?!\*\*\*)\d{4,}")


@pytest.fixture(autouse=True)
def isolated_shared(tmp_path, monkeypatch):
    """Point the shared protocol at an isolated tmp_path filesystem and reset in-memory state."""
    monkeypatch.setenv("PIPELINE_SHARED_ROOT", str(tmp_path / "shared"))
    monkeypatch.setenv("PIPELINE_LOGS_DIR", str(tmp_path / "logs"))
    protocol.ensure_dirs()
    frontend_server.LIVE.clear()
    yield
    frontend_server.LIVE.clear()


def _synthetic_payload(**overrides) -> dict:
    payload = {
        "amount": "250.00",
        "currency": "USD",
        "source_account": "ACC-1111",
        "destination_account": "ACC-2222",
        "transaction_type": "transfer",
        "description": "API gateway test",
        "metadata": {"channel": "api", "country": "US"},
        "timestamp": "2026-07-09T12:00:00Z",
    }
    payload.update(overrides)
    return payload


def _poll_until_terminal(client: TestClient, txn_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict | None = None
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/transactions/{txn_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last.get("stage") == "results":
            return last
        time.sleep(0.02)
    raise AssertionError(f"transaction {txn_id} never reached a terminal stage: {last}")


def test_post_valid_payload_returns_202_and_eventually_terminal():
    with TestClient(frontend_server.app) as client:
        resp = client.post("/api/v1/transactions", json=_synthetic_payload())
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "accepted"
        txn_id = body["transaction_id"]
        assert txn_id
        assert body["status_url"] == f"/api/v1/transactions/{txn_id}"

        final = _poll_until_terminal(client, txn_id)
        assert final["stage"] == "results"
        assert final["outcome"] in {"cleared", "flagged", "rejected"}


def test_post_missing_required_field_returns_422_and_writes_nothing():
    with TestClient(frontend_server.app) as client:
        payload = _synthetic_payload()
        del payload["amount"]

        resp = client.post("/api/v1/transactions", json=payload)
        assert resp.status_code == 422
        errors = resp.json()["errors"]
        assert any(e["field"] == "amount" for e in errors)

        # Rejected before ever reaching the pipeline -- no file written to shared/input/.
        assert protocol.list_messages("input") == []


def test_post_blank_transaction_id_is_rejected_as_structurally_invalid():
    with TestClient(frontend_server.app) as client:
        payload = _synthetic_payload(transaction_id="   ")
        resp = client.post("/api/v1/transactions", json=payload)
        assert resp.status_code == 422
        errors = resp.json()["errors"]
        assert any(e["field"] == "transaction_id" for e in errors)


def test_post_resubmitting_terminal_transaction_returns_200_without_duplicating():
    with TestClient(frontend_server.app) as client:
        payload = _synthetic_payload(transaction_id="TXN-GATEWAY-DUP")
        resp = client.post("/api/v1/transactions", json=payload)
        assert resp.status_code == 202
        _poll_until_terminal(client, "TXN-GATEWAY-DUP")

        resp2 = client.post("/api/v1/transactions", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["transaction_id"] == "TXN-GATEWAY-DUP"

        # Exactly one result file for this transaction_id -- no duplicate.
        result_files = [
            p for p in protocol.list_messages("results") if p.stem == "TXN-GATEWAY-DUP"
        ]
        assert len(result_files) == 1


def test_get_unknown_transaction_returns_404():
    with TestClient(frontend_server.app) as client:
        resp = client.get("/api/v1/transactions/DOES-NOT-EXIST")
        assert resp.status_code == 404


def test_get_transactions_list_supports_status_and_decision_filters():
    with TestClient(frontend_server.app) as client:
        resp = client.post(
            "/api/v1/transactions", json=_synthetic_payload(transaction_id="TXN-GATEWAY-LIST")
        )
        assert resp.status_code == 202
        final = _poll_until_terminal(client, "TXN-GATEWAY-LIST")

        listed = client.get("/api/v1/transactions").json()
        assert any(e["transaction_id"] == "TXN-GATEWAY-LIST" for e in listed)

        filtered = client.get(
            "/api/v1/transactions", params={"decision": final["decision"]}
        ).json()
        assert any(e["transaction_id"] == "TXN-GATEWAY-LIST" for e in filtered)

        empty = client.get(
            "/api/v1/transactions", params={"decision": "__no_such_decision__"}
        ).json()
        assert all(e["transaction_id"] != "TXN-GATEWAY-LIST" for e in empty)


def test_no_response_body_contains_an_unmasked_account_number():
    with TestClient(frontend_server.app) as client:
        payload = _synthetic_payload(
            transaction_id="TXN-GATEWAY-PII",
            source_account="ACC-13571113",
            destination_account="ACC-24681012",
        )
        resp = client.post("/api/v1/transactions", json=payload)
        assert not _UNMASKED_ACCOUNT_PATTERN.search(resp.text)

        final = _poll_until_terminal(client, "TXN-GATEWAY-PII")
        assert not _UNMASKED_ACCOUNT_PATTERN.search(str(final))

        list_resp = client.get("/api/v1/transactions")
        assert list_resp.status_code == 200
        assert not _UNMASKED_ACCOUNT_PATTERN.search(list_resp.text)
