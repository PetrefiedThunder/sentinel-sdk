"""Offline backend QA; strict expected failures document unresolved findings.

All HTTP uses MockTransport; credentials, ids and hosts are random per run
(tests/_qa_values.py) and hosts are never resolved.
"""

import asyncio
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

import sentinel.client as client_module
import sentinel.decorator as decorator_module
from sentinel import (
    ApprovalRejected,
    ApprovalTimeout,
    SentinelAPIError,
    SentinelClient,
    SentinelConfig,
    SentinelConfigError,
    oversight,
)
from tests._qa_values import (
    ACTION_ID,
    AMOUNTS,
    API_KEYS,
    CONTACT_ID,
    CREDENTIAL_MARKER,
    ERR_DETAIL,
    ERR_OPERATION,
    ERR_TRANSPORT,
    ERROR_TEXT,
    HOSTS,
    ITEM,
    RECIPIENT,
    REPLAY_KEY,
    REQUEST_IDS,
    RESULT_TEXT,
    TASK_NAME,
    rclock,
    rhex,
    rid,
    rseconds,
)


@pytest.fixture
def client_factory():
    clients = []

    def make(handler, *, label="one"):
        config = SentinelConfig(api_key=API_KEYS[label], api_url=f"https://{HOSTS[label]}")
        client = SentinelClient(config)
        client._client = httpx.Client(
            base_url=config.api_url,
            headers=client._headers(),
            transport=httpx.MockTransport(handler),
        )
        client._aclient = httpx.AsyncClient(
            base_url=config.api_url,
            headers=client._headers(),
            transport=httpx.MockTransport(handler),
        )
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
        asyncio.run(client.aclose())


def invoke(client, mode, method, *args, **kwargs):
    if mode == "async":
        return asyncio.run(getattr(client, "a" + method)(*args, **kwargs))
    return getattr(client, method)(*args, **kwargs)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 500, 503])
def test_http_errors_preserve_status_without_retry(client_factory, mode, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": ERR_DETAIL})

    client = client_factory(handler)
    with pytest.raises(SentinelAPIError) as error:
        invoke(client, mode, "create_approval", TASK_NAME, {}, idempotency_key=REPLAY_KEY)
    assert error.value.status_code == status
    assert ERR_DETAIL in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("body", ["plain text", ["error"], {"message": "failure"}])
def test_error_body_shapes_are_not_swallowed(client_factory, body):
    def handler(request):
        if isinstance(body, str):
            return httpx.Response(502, text=body)
        return httpx.Response(502, json=body)

    with pytest.raises(SentinelAPIError) as error:
        client_factory(handler).get_approval(ACTION_ID)
    assert error.value.status_code == 502
    expected = body["message"] if isinstance(body, dict) else str(body)
    assert expected in str(error.value)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_transport_failure_never_replays_approval(client_factory, mode, error_type):
    calls = []

    def handler(request):
        calls.append(request)
        raise error_type(ERR_TRANSPORT, request=request)

    with pytest.raises(error_type):
        invoke(client_factory(handler), mode, "create_approval", TASK_NAME, {})
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_missing_key_fails_before_constructing_transport(monkeypatch, mode):
    constructor = MagicMock(side_effect=AssertionError("network client must not be constructed"))
    # Header validation occurs while evaluating the constructor arguments.
    monkeypatch.setattr(httpx, "AsyncClient" if mode == "async" else "Client", constructor)
    client = SentinelClient(SentinelConfig(api_key=None, api_url=f"https://{HOSTS['one']}"))
    with pytest.raises(SentinelConfigError):
        invoke(client, mode, "create_approval", TASK_NAME, {})
    constructor.assert_not_called()


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_legacy_wait_fallback_returns_terminal_decision(client_factory, mode, status):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/wait"):
            return httpx.Response(404, json={"detail": "legacy server"})
        return httpx.Response(200, json={"status": status})

    decision = invoke(client_factory(handler), mode, "wait_for_decision", ACTION_ID)
    assert decision["status"] == status
    assert paths == [f"/v1/approvals/{ACTION_ID}/wait", f"/v1/approvals/{ACTION_ID}"]


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_legacy_wait_paces_pending_requests(client_factory, monkeypatch, mode):
    polls = []
    sleeper = MagicMock()
    async_sleeper = AsyncMock()
    start = rclock()
    monkeypatch.setattr(
        client_module, "time", SimpleNamespace(monotonic=lambda: start, sleep=sleeper)
    )
    monkeypatch.setattr(asyncio, "sleep", async_sleeper)

    def handler(request):
        if request.url.path.endswith("/wait"):
            return httpx.Response(404, json={"detail": "legacy server"})
        polls.append(request)
        return httpx.Response(200, json={"status": "pending" if len(polls) == 1 else "approved"})

    invoke(
        client_factory(handler), mode, "wait_for_decision", ACTION_ID, timeout=5, poll_interval=2
    )
    if mode == "async":
        async_sleeper.assert_awaited_once_with(2)
    else:
        sleeper.assert_called_once_with(2)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-005: an approved response after the deadline is accepted",
)
def test_late_approval_does_not_bypass_deadline(client_factory, monkeypatch, mode):
    start = rclock()
    clock = {"now": start}
    monkeypatch.setattr(client_module, "time", SimpleNamespace(monotonic=lambda: clock["now"]))

    def handler(request):
        clock["now"] = start + 1 + rseconds()
        return httpx.Response(200, json={"status": "approved"})

    try:
        invoke(client_factory(handler), mode, "wait_for_decision", ACTION_ID, timeout=1)
    except ApprovalTimeout:
        return
    assert False, "approval returned after the caller's one-second deadline"


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_pending_decision_raises_timeout_with_context(client_factory, monkeypatch, mode):
    start = rclock()
    clock = {"now": start}
    monkeypatch.setattr(client_module, "time", SimpleNamespace(monotonic=lambda: clock["now"]))

    def handler(request):
        clock["now"] = start + 1 + rseconds()
        return httpx.Response(200, json={"status": "pending"})

    with pytest.raises(ApprovalTimeout) as error:
        invoke(client_factory(handler), mode, "wait_for_decision", ACTION_ID, timeout=1)
    assert error.value.action_id == ACTION_ID
    assert error.value.timeout_seconds == 1


@pytest.mark.asyncio
async def test_concurrent_clients_keep_identity_and_idempotency_isolated(client_factory):
    seen = []

    def handler(request):
        seen.append(
            (request.url.host, request.headers["Authorization"], request.headers["Idempotency-Key"])
        )
        return httpx.Response(200, json={"action_id": request.headers["Idempotency-Key"]})

    one = client_factory(handler, label="one")
    two = client_factory(handler, label="two")
    results = await asyncio.gather(
        one.acreate_approval(TASK_NAME, {}, idempotency_key=REQUEST_IDS["one"]),
        two.acreate_approval(TASK_NAME, {}, idempotency_key=REQUEST_IDS["two"]),
    )
    assert {result["action_id"] for result in results} == {REQUEST_IDS["one"], REQUEST_IDS["two"]}
    assert set(seen) == {
        (HOSTS["one"], f"Bearer {API_KEYS['one']}", REQUEST_IDS["one"]),
        (HOSTS["two"], f"Bearer {API_KEYS['two']}", REQUEST_IDS["two"]),
    }


def decorator_client(monkeypatch, mode, *, decision=None, failure=None):
    client = MagicMock()
    client.create_approval.return_value = {"action_id": ACTION_ID}
    client.acreate_approval = AsyncMock(return_value={"action_id": ACTION_ID})
    client.wait_for_decision.return_value = decision
    client.wait_for_decision.side_effect = failure
    client.await_for_decision = AsyncMock(return_value=decision, side_effect=failure)
    client.aemit_audit_event = AsyncMock()
    client.aclose = AsyncMock()
    monkeypatch.setattr(decorator_module, "SentinelClient", lambda config: client)
    monkeypatch.setattr(decorator_module, "get_config", lambda: SentinelConfig(fallback="reject"))
    return client


def wrap_call(mode, function, **kwargs):
    if mode == "async":

        async def operation():
            return function()

        return lambda: asyncio.run(oversight(**kwargs)(operation)())

    def operation():
        return function()

    return oversight(**kwargs)(operation)


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("missing", ["positional", "keyword-only"])
def test_missing_arguments_never_request_approval(monkeypatch, mode, missing):
    """UX-003: required arguments fail before either sync or async approval."""
    client = decorator_client(monkeypatch, mode, decision={"status": "approved"})
    calls = []

    def operation(amount, recipient, *, memo):
        calls.append((amount, recipient, memo))

    async def async_operation(amount, recipient, *, memo):
        operation(amount, recipient, memo=memo)

    wrapped = oversight()(async_operation if mode == "async" else operation)
    args, kwargs = (
        ((AMOUNTS["one"],), {"memo": ITEM})
        if missing == "positional"
        else ((AMOUNTS["one"], RECIPIENT), {})
    )
    with pytest.raises(TypeError, match="required.*argument"):
        if mode == "async":
            asyncio.run(wrapped(*args, **kwargs))
        else:
            wrapped(*args, **kwargs)
    assert calls == []
    client.create_approval.assert_not_called()
    client.acreate_approval.assert_not_called()
    client.wait_for_decision.assert_not_called()
    client.await_for_decision.assert_not_called()


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "decision",
    [
        {"status": "rejected"},
        {"status": "unknown"},
        {},
        {"status": "rejected", "decision": "approved"},
    ],
)
def test_unapproved_decisions_never_execute(monkeypatch, mode, decision):
    decorator_client(monkeypatch, mode, decision=decision)
    operation = MagicMock()
    with pytest.raises(ApprovalRejected):
        wrap_call(mode, operation)()
    operation.assert_not_called()


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_default_timeout_never_executes(monkeypatch, mode):
    decorator_client(monkeypatch, mode, failure=ApprovalTimeout(ACTION_ID, 1))
    operation = MagicMock()
    with pytest.raises(ApprovalTimeout):
        wrap_call(mode, operation)()
    operation.assert_not_called()


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    "failure", [SentinelAPIError(403, "denied"), httpx.ReadTimeout(ERR_TRANSPORT)]
)
def test_execute_fallback_does_not_bypass_api_or_network_failures(monkeypatch, mode, failure):
    decorator_client(monkeypatch, mode, failure=failure)
    operation = MagicMock()
    with pytest.raises(type(failure)):
        wrap_call(mode, operation, fallback="execute")()
    operation.assert_not_called()


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("outcome", ["approved", "rejected", "timeout", "operation-error"])
@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="BE-002: decorator-owned clients are never closed"
)
def test_decorator_closes_client_on_every_exit(monkeypatch, mode, outcome):
    client = decorator_client(
        monkeypatch,
        mode,
        decision={"status": "rejected" if outcome == "rejected" else "approved"},
        failure=ApprovalTimeout(ACTION_ID, 1) if outcome == "timeout" else None,
    )

    def operation():
        if outcome == "operation-error":
            raise ValueError(ERR_OPERATION)
        return "ok"

    with contextlib.suppress(ApprovalRejected, ApprovalTimeout, ValueError):
        wrap_call(mode, operation)()
    if mode == "async":
        client.aclose.assert_awaited_once()
    else:
        client.close.assert_called_once()


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_timeout_fallback_exception_is_audited(monkeypatch, mode):
    """BE-003: failed explicit fallback must preserve the error and audit attempt."""
    client = decorator_client(monkeypatch, mode, failure=ApprovalTimeout(ACTION_ID, 1))
    original_error = ValueError(ERR_OPERATION)
    operation = MagicMock(side_effect=original_error)

    with pytest.raises(ValueError, match=ERR_OPERATION) as raised:
        wrap_call(mode, operation, fallback="execute")()
    assert raised.value is original_error
    operation.assert_called_once_with()
    audit = client.aemit_audit_event if mode == "async" else client.emit_audit_event
    audit.assert_called_once()
    if mode == "async":
        audit.assert_awaited_once()
    assert audit.call_args.args[0] == ACTION_ID
    assert audit.call_args.kwargs["execution_result"] is None
    assert "timeout-fallback-execute" in audit.call_args.kwargs["error"]
    assert ERR_OPERATION in audit.call_args.kwargs["error"]


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_timeout_fallback_success_is_audited(monkeypatch, mode):
    """BE-003: successful explicit fallback keeps its existing result and audit."""
    client = decorator_client(monkeypatch, mode, failure=ApprovalTimeout(ACTION_ID, 1))
    operation = MagicMock(return_value="success")

    assert wrap_call(mode, operation, fallback="execute")() == "success"
    operation.assert_called_once_with()
    audit = client.aemit_audit_event if mode == "async" else client.emit_audit_event
    audit.assert_called_once_with(
        ACTION_ID, execution_result="'success'", error="timeout-fallback-execute"
    )
    if mode == "async":
        audit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="BE-004: mutable arguments can change while approval is pending",
)
async def test_execution_arguments_match_approved_snapshot(client_factory, monkeypatch):
    approval_requested = asyncio.Event()
    mutation_done = asyncio.Event()
    observed = {}
    arguments = {"amount": AMOUNTS["one"]}

    async def handler(request):
        if request.url.path == "/v1/approvals":
            observed["approved"] = json.loads(request.content)["arguments"]["payload"]["amount"]
            return httpx.Response(200, json={"action_id": ACTION_ID})
        if request.url.path.endswith("/wait"):
            approval_requested.set()
            await mutation_done.wait()
            return httpx.Response(200, json={"status": "approved"})
        return httpx.Response(200, json={})

    client = client_factory(handler)
    monkeypatch.setattr(decorator_module, "SentinelClient", lambda config: client)

    @oversight()
    async def operation(payload):
        observed["executed"] = payload["amount"]

    async def concurrent_mutation():
        await approval_requested.wait()
        arguments["amount"] = AMOUNTS["one"] + AMOUNTS["two"]
        mutation_done.set()

    await asyncio.gather(operation(arguments), concurrent_mutation())
    assert observed["executed"] == observed["approved"]


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_are_rejected_before_transport(client_factory, mode, value):
    handler = MagicMock(return_value=httpx.Response(200, json={"action_id": ACTION_ID}))
    with pytest.raises(ValueError):
        invoke(client_factory(handler), mode, "create_approval", TASK_NAME, {"amount": value})
    handler.assert_not_called()


def test_json_payload_roundtrip_property(client_factory):
    hypothesis = pytest.importorskip("hypothesis")
    from hypothesis import strategies as st

    received = []

    def handler(request):
        received.append(json.loads(request.content)["arguments"])
        return httpx.Response(200, json={"action_id": ACTION_ID})

    client = client_factory(handler)
    scalars = (
        st.none()
        | st.booleans()
        | st.integers()
        | st.floats(allow_nan=False, allow_infinity=False)
        | st.text()
    )
    values = st.recursive(
        scalars,
        lambda children: (
            st.lists(children, max_size=5) | st.dictionaries(st.text(), children, max_size=5)
        ),
        max_leaves=15,
    )

    @hypothesis.settings(max_examples=75, derandomize=True, database=None, deadline=None)
    @hypothesis.given(values)
    def check(arguments):
        client.create_approval(TASK_NAME, arguments)
        assert received[-1] == arguments

    check()


@pytest.mark.asyncio
async def test_shared_client_keeps_concurrent_request_keys_isolated(client_factory):
    received = {}

    async def handler(request):
        await asyncio.sleep(0)
        key = request.headers["Idempotency-Key"]
        received[key] = json.loads(request.content)["arguments"]["request"]
        return httpx.Response(200, json={"action_id": key})

    client = client_factory(handler)
    keys = [rid() for _ in range(10)]
    values = [rhex() for _ in keys]
    await asyncio.gather(
        *(
            client.acreate_approval(TASK_NAME, {"request": value}, idempotency_key=key)
            for key, value in zip(keys, values, strict=True)
        )
    )
    assert received == dict(zip(keys, values, strict=True))


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    ("method", "args", "verb", "path", "payload"),
    [
        ("get_tenant", (), "GET", "/v1/tenants/me", None),
        (
            "set_default_approvers",
            ([""],),
            "PATCH",
            "/v1/tenants/me",
            {"default_approvers": [""]},
        ),
        (
            "register_sms_contact",
            ("", "", ""),
            "POST",
            "/v1/approver-contacts",
            {
                "phone_number": "",
                "display_name": "",
                "consent_source": "",
                "consent_note": "",
                "consent_attested": True,
            },
        ),
        ("list_sms_contacts", (), "GET", "/v1/approver-contacts", None),
        (
            "revoke_sms_contact",
            (CONTACT_ID,),
            "DELETE",
            f"/v1/approver-contacts/{CONTACT_ID}",
            None,
        ),
        ("list_audit_events", (), "GET", "/v1/audit-events", None),
        (
            "emit_audit_event",
            (ACTION_ID, RESULT_TEXT, ERROR_TEXT),
            "POST",
            "/v1/audit-events",
            {
                "action_id": ACTION_ID,
                "execution_result": RESULT_TEXT,
                "error": ERROR_TEXT,
            },
        ),
    ],
)
def test_supporting_endpoint_contracts(client_factory, mode, method, args, verb, path, payload):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[] if method.startswith("list_") else {})

    invoke(client_factory(handler), mode, method, *args)
    assert len(seen) == 1
    assert seen[0].method == verb
    assert seen[0].url.path == path
    if payload is not None:
        assert json.loads(seen[0].content) == payload


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_audit_transport_errors_remain_best_effort(client_factory, mode):
    def handler(request):
        raise httpx.ConnectError(ERR_TRANSPORT, request=request)

    assert invoke(client_factory(handler), mode, "emit_audit_event", ACTION_ID) is None


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="BE-006: config repr contains the credential value"
)
def test_config_repr_omits_credential():
    credential_marker = CREDENTIAL_MARKER
    config = SentinelConfig(api_key=credential_marker, api_url=f"https://{HOSTS['one']}")
    assert credential_marker not in repr(config)
