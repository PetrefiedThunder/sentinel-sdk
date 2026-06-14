"""list_approvals / list_audit_events_page parity + timeout_seconds int coercion.

All HTTP is mocked with httpx.MockTransport so these run offline. The live API
(https://api.pauseapi.app/openapi.json) types ApprovalCreate.timeout_seconds as
an integer (default 300) and 422s on a fractional value, and the GET
/v1/approvals + GET /v1/audit-events endpoints accept status/action_id, limit,
and cursor query params returning a {data, has_more, next_cursor} envelope.
"""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from sentinel import PageResult, SentinelClient
from sentinel.config import SentinelConfig

_PAGE_BODY = {
    "data": [{"action_id": "act_1"}, {"action_id": "act_2"}],
    "has_more": True,
    "next_cursor": "cur_abc",
}


def _make_client(captured: list, *, body=_PAGE_BODY, status_code=200) -> SentinelClient:
    """Real SentinelClient backed by an httpx MockTransport that records requests."""
    client = SentinelClient(SentinelConfig(api_key="sk_test", api_url="https://api.test"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(status_code, json=body)

    client._client = httpx.Client(
        base_url="https://api.test",
        headers=client._headers(),
        transport=httpx.MockTransport(handler),
    )
    client._aclient = httpx.AsyncClient(
        base_url="https://api.test",
        headers=client._headers(),
        transport=httpx.MockTransport(handler),
    )
    return client


def _query(request: httpx.Request) -> dict:
    return {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}


# ------------- timeout_seconds int coercion -------------
def test_create_approval_coerces_fractional_timeout_to_int():
    captured = []
    client = _make_client(captured, body={"action_id": "act_1", "status": "pending"})
    client.create_approval(function_name="t", arguments={"a": 1}, timeout_seconds=1.9)
    payload = json.loads(captured[0].content)
    assert payload["timeout_seconds"] == 1
    assert isinstance(payload["timeout_seconds"], int)


def test_create_approval_coerces_float_config_default_to_int():
    captured = []
    # config default timeout is a float (300.0); the wire value must be an int.
    client = _make_client(captured, body={"action_id": "act_1", "status": "pending"})
    client.config.timeout_seconds = 300.0
    client.create_approval(function_name="t", arguments={"a": 1})
    payload = json.loads(captured[0].content)
    assert payload["timeout_seconds"] == 300
    assert isinstance(payload["timeout_seconds"], int)


@pytest.mark.asyncio
async def test_acreate_approval_coerces_fractional_timeout_to_int():
    captured = []
    client = _make_client(captured, body={"action_id": "act_1", "status": "pending"})
    await client.acreate_approval(function_name="t", arguments={"a": 1}, timeout_seconds=2.7)
    payload = json.loads(captured[0].content)
    assert payload["timeout_seconds"] == 2
    assert isinstance(payload["timeout_seconds"], int)


# ------------- list_approvals -------------
def test_list_approvals_returns_typed_page():
    captured = []
    client = _make_client(captured)
    page = client.list_approvals()
    assert isinstance(page, PageResult)
    assert page.data == _PAGE_BODY["data"]
    assert page.has_more is True
    assert page.next_cursor == "cur_abc"


def test_list_approvals_sends_default_limit():
    captured = []
    client = _make_client(captured)
    client.list_approvals()
    q = _query(captured[0])
    assert captured[0].url.path == "/v1/approvals"
    assert q["limit"] == "50"
    assert "cursor" not in q
    assert "status" not in q


def test_list_approvals_sends_status_limit_cursor():
    captured = []
    client = _make_client(captured)
    client.list_approvals(status="pending", limit=10, cursor="cur_xyz")
    q = _query(captured[0])
    assert q["status"] == "pending"
    assert q["limit"] == "10"
    assert q["cursor"] == "cur_xyz"


def test_list_approvals_tolerates_bare_list():
    captured = []
    client = _make_client(captured, body=[{"action_id": "act_1"}])
    page = client.list_approvals()
    assert page.data == [{"action_id": "act_1"}]
    assert page.has_more is False
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_alist_approvals_returns_typed_page():
    captured = []
    client = _make_client(captured)
    page = await client.alist_approvals(status="approved", limit=5, cursor="c1")
    assert isinstance(page, PageResult)
    assert page.next_cursor == "cur_abc"
    q = _query(captured[0])
    assert q == {"status": "approved", "limit": "5", "cursor": "c1"}


# ------------- list_audit_events_page -------------
def test_list_audit_events_page_sends_default_limit():
    captured = []
    client = _make_client(captured)
    page = client.list_audit_events_page()
    assert isinstance(page, PageResult)
    q = _query(captured[0])
    assert captured[0].url.path == "/v1/audit-events"
    assert q["limit"] == "50"


def test_list_audit_events_page_sends_action_id_limit_cursor():
    captured = []
    client = _make_client(captured)
    client.list_audit_events_page(action_id="act_9", limit=100, cursor="cur_2")
    q = _query(captured[0])
    assert q == {"action_id": "act_9", "limit": "100", "cursor": "cur_2"}


@pytest.mark.asyncio
async def test_alist_audit_events_page_returns_typed_page():
    captured = []
    client = _make_client(captured)
    page = await client.alist_audit_events_page(limit=25)
    assert isinstance(page, PageResult)
    assert page.has_more is True
    q = _query(captured[0])
    assert q["limit"] == "25"
