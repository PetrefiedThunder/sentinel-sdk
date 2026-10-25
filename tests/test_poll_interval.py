"""Fallback polling honors poll_interval and the config default.

When GET /v1/approvals/{id}/wait returns 404, wait_for_decision and
await_for_decision poll GET /v1/approvals/{id}. That path must sleep for the
explicit interval (or SentinelConfig.poll_interval), and the sleep must not
run past the decision deadline. A terminal status returns without sleeping.
Long-poll responses are not delayed.
"""

import httpx
import pytest

from sentinel.client import SentinelClient
from sentinel.config import SentinelConfig
from sentinel.exceptions import ApprovalTimeout


class _Clock:
    def __init__(self) -> None:
        self.t = 1_000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


def _install_clock(monkeypatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr("sentinel.client.time.monotonic", clock.monotonic)
    monkeypatch.setattr("sentinel.client.time.sleep", clock.sleep)
    monkeypatch.setattr("sentinel.client.asyncio.sleep", clock.asleep)
    return clock


def _client(
    handler, *, poll_interval: float = 2.0, timeout_seconds: float = 30.0
) -> SentinelClient:
    client = SentinelClient(
        SentinelConfig(
            api_key="sk_test",
            api_url="https://api.test",
            poll_interval=poll_interval,
            timeout_seconds=timeout_seconds,
        )
    )
    transport = httpx.MockTransport(handler)
    client._client = httpx.Client(base_url="https://api.test", transport=transport)
    client._aclient = httpx.AsyncClient(base_url="https://api.test", transport=transport)
    return client


def _fallback_then(statuses: list[str]):
    """404 every /wait; each status GET consumes the next body."""
    pending = list(statuses)
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/wait"):
            return httpx.Response(404, json={"detail": "missing"})
        status = pending.pop(0) if pending else "pending"
        return httpx.Response(200, json={"action_id": "act_1", "status": status})

    return handler, paths


def test_fallback_sleeps_explicit_poll_interval(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, paths = _fallback_then(["pending", "approved"])
    client = _client(handler, poll_interval=9.0)
    data = client.wait_for_decision("act_1", timeout=30, poll_interval=2)
    assert data["status"] == "approved"
    assert clock.sleeps == [2.0]
    assert paths == [
        "/v1/approvals/act_1/wait",
        "/v1/approvals/act_1",
        "/v1/approvals/act_1/wait",
        "/v1/approvals/act_1",
    ]


def test_fallback_sleeps_config_default_when_interval_omitted(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, _paths = _fallback_then(["pending", "approved"])
    client = _client(handler, poll_interval=3.5)
    data = client.wait_for_decision("act_1", timeout=30)
    assert data["status"] == "approved"
    assert clock.sleeps == [3.5]


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_fallback_terminal_status_returns_without_sleep(monkeypatch, status):
    clock = _install_clock(monkeypatch)
    handler, paths = _fallback_then([status])
    client = _client(handler)
    data = client.wait_for_decision("act_1", timeout=30, poll_interval=2)
    assert data["status"] == status
    assert clock.sleeps == []
    assert paths == ["/v1/approvals/act_1/wait", "/v1/approvals/act_1"]


def test_fallback_sleep_stops_at_deadline(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, paths = _fallback_then(["pending", "pending", "pending"])
    client = _client(handler, poll_interval=2.0)
    with pytest.raises(ApprovalTimeout):
        client.wait_for_decision("act_1", timeout=1, poll_interval=8)
    assert clock.sleeps == [1.0]
    assert paths == ["/v1/approvals/act_1/wait", "/v1/approvals/act_1"]


def test_long_poll_pending_does_not_sleep(monkeypatch):
    clock = _install_clock(monkeypatch)
    bodies = iter(
        [
            {"action_id": "act_1", "status": "pending"},
            {"action_id": "act_1", "status": "approved"},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/wait")
        return httpx.Response(200, json=next(bodies))

    client = _client(handler)
    data = client.wait_for_decision("act_1", timeout=30, poll_interval=2)
    assert data["status"] == "approved"
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_async_fallback_sleeps_explicit_poll_interval(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, _paths = _fallback_then(["pending", "approved"])
    client = _client(handler, poll_interval=9.0)
    data = await client.await_for_decision("act_1", timeout=30, poll_interval=2)
    assert data["status"] == "approved"
    assert clock.sleeps == [2.0]


@pytest.mark.asyncio
async def test_async_fallback_sleeps_config_default(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, _paths = _fallback_then(["pending", "rejected"])
    client = _client(handler, poll_interval=4.0)
    data = await client.await_for_decision("act_1", timeout=30)
    assert data["status"] == "rejected"
    assert clock.sleeps == [4.0]


@pytest.mark.asyncio
async def test_async_fallback_terminal_returns_without_sleep(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, _paths = _fallback_then(["approved"])
    client = _client(handler)
    data = await client.await_for_decision("act_1", timeout=30, poll_interval=2)
    assert data["status"] == "approved"
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_async_fallback_sleep_stops_at_deadline(monkeypatch):
    clock = _install_clock(monkeypatch)
    handler, paths = _fallback_then(["pending", "pending"])
    client = _client(handler)
    with pytest.raises(ApprovalTimeout):
        await client.await_for_decision("act_1", timeout=1, poll_interval=8)
    assert clock.sleeps == [1.0]
    assert paths == ["/v1/approvals/act_1/wait", "/v1/approvals/act_1"]
