"""Execution audits use the supported API's string-result wire contract."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from sentinel import ApprovalTimeout, SentinelClient, oversight
from sentinel.config import SentinelConfig


@pytest.mark.asyncio
@pytest.mark.parametrize("is_async", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("decision", ["approved", "timeout"])
@pytest.mark.parametrize("outcome", ["error", "result", "none"])
async def test_execution_audit_wire_contract(monkeypatch, is_async, decision, outcome):
    audit_payloads = []
    executions = []

    def handler(request):
        if request.url.path == "/v1/approvals":
            return httpx.Response(200, json={"action_id": "act_audit"})
        if request.url.path == "/v1/approvals/act_audit/wait":
            return httpx.Response(200, json={"status": "approved"})
        if request.url.path == "/v1/audit-events":
            audit_payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "evt_audit"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    config = SentinelConfig(api_key="synthetic-test", api_url="https://audit.invalid")
    client = SentinelClient(config)
    monkeypatch.setattr("sentinel.decorator.SentinelClient", lambda _config: client)
    if decision == "timeout":
        timeout = ApprovalTimeout("act_audit", 1)
        monkeypatch.setattr(client, "wait_for_decision", MagicMock(side_effect=timeout))
        monkeypatch.setattr(client, "await_for_decision", AsyncMock(side_effect=timeout))

    original_error = RuntimeError("synthetic function failed")
    result = {"completed": True} if outcome == "result" else None

    def execute():
        executions.append("executed")
        if outcome == "error":
            raise original_error
        return result

    async def aexecute():
        return execute()

    wrapped = oversight(fallback="execute" if decision == "timeout" else "reject")(
        aexecute if is_async else execute
    )
    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url=config.api_url, transport=transport) as sync_http:
        async with httpx.AsyncClient(base_url=config.api_url, transport=transport) as async_http:
            client._client = sync_http
            client._aclient = async_http
            if outcome == "error":
                with pytest.raises(RuntimeError) as caught:
                    if is_async:
                        await wrapped()
                    else:
                        wrapped()
                assert caught.value is original_error
            else:
                actual = await wrapped() if is_async else wrapped()
                assert actual is result

    expected_error = repr(original_error) if outcome == "error" else None
    if decision == "timeout":
        expected_error = "timeout-fallback-execute" + (
            f": {expected_error}" if expected_error else ""
        )
    assert executions == ["executed"]
    # API AuditEventCreate requires execution_result: str even on failure.
    # None uses the representation already sent for a successful None result.
    assert audit_payloads == [
        {
            "action_id": "act_audit",
            "execution_result": repr(result),
            "error": expected_error,
        }
    ]
