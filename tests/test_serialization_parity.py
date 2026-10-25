"""SEL-233 — every entry point rejects non-JSON arguments the same way.

The direct client, @oversight (sync + async) and the crewai/autogen adapters
must all raise TypeError before any approval request reaches the network.
"""

from unittest.mock import patch

import httpx
import pytest

from sentinel import SentinelClient, oversight
from sentinel.adapters import autogen, crewai
from sentinel.config import SentinelConfig


class _Custom:
    pass


BAD_VALUES = [
    pytest.param({1, 2}, "set", id="set"),
    pytest.param(b"raw", "bytes", id="bytes"),
    pytest.param(_Custom(), "_Custom", id="custom-object"),
]


@pytest.fixture
def recorded():
    """Real SentinelClient whose HTTP transports record every request."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"action_id": "act_1", "status": "approved"})

    client = SentinelClient(SentinelConfig(api_key="sk_test", api_url="https://api.test"))
    client._client = httpx.Client(
        base_url="https://api.test", transport=httpx.MockTransport(handler)
    )
    client._aclient = httpx.AsyncClient(
        base_url="https://api.test", transport=httpx.MockTransport(handler)
    )
    return client, requests


@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
def test_direct_client(recorded, value, type_name):
    client, requests = recorded
    with pytest.raises(TypeError, match="JSON-serializable"):
        client.create_approval(function_name="tool", arguments={"x": value})
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
async def test_direct_client_async(recorded, value, type_name):
    client, requests = recorded
    with pytest.raises(TypeError, match="JSON-serializable"):
        await client.acreate_approval(function_name="tool", arguments={"x": value})
    assert requests == []


@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
def test_oversight_sync(recorded, value, type_name):
    client, requests = recorded
    ran = []

    @oversight()
    def tool(x):
        ran.append(x)

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match=rf"arguments\['x'\] is of type {type_name}"),
    ):
        tool(value)
    assert requests == []
    assert ran == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
async def test_oversight_async(recorded, value, type_name):
    client, requests = recorded
    ran = []

    @oversight()
    async def tool(x):
        ran.append(x)

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match=rf"arguments\['x'\] is of type {type_name}"),
    ):
        await tool(value)
    assert requests == []
    assert ran == []


@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
def test_crewai_gated(recorded, value, type_name):
    client, requests = recorded
    ran = []

    def tool(x):
        ran.append(x)

    wrapped = crewai.gated(tool, client=client)
    with pytest.raises(TypeError, match="JSON-serializable"):
        wrapped(x=value)
    assert requests == []
    assert ran == []


@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
def test_autogen_gated_sync(recorded, value, type_name):
    client, requests = recorded
    ran = []

    @autogen.gated(client=client)
    def tool(x):
        ran.append(x)

    with pytest.raises(TypeError, match="JSON-serializable"):
        tool(x=value)
    assert requests == []
    assert ran == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("value", "type_name"), BAD_VALUES)
async def test_autogen_gated_async(recorded, value, type_name):
    client, requests = recorded
    ran = []

    @autogen.gated(client=client)
    async def tool(x):
        ran.append(x)

    with pytest.raises(TypeError, match="JSON-serializable"):
        await tool(x=value)
    assert requests == []
    assert ran == []


def test_oversight_error_names_nested_path(recorded):
    client, requests = recorded

    @oversight()
    def tool(payload):
        pass

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match=r"arguments\['payload'\]\['meta'\]\[1\] is of type set"),
    ):
        tool({"meta": ["ok", {1}]})
    assert requests == []


def test_oversight_rejects_non_primitive_dict_key(recorded):
    client, requests = recorded

    @oversight()
    def tool(payload):
        pass

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match="key of type tuple"),
    ):
        tool({(1, 2): "v"})
    assert requests == []


NON_FINITE = [
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="inf"),
    pytest.param(float("-inf"), id="-inf"),
]


@pytest.mark.parametrize("value", NON_FINITE)
def test_direct_client_rejects_non_finite_float(recorded, value):
    client, requests = recorded
    with pytest.raises(TypeError, match="JSON-serializable"):
        client.create_approval(function_name="tool", arguments={"x": [value]})
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NON_FINITE)
async def test_direct_client_async_rejects_non_finite_float(recorded, value):
    client, requests = recorded
    with pytest.raises(TypeError, match="JSON-serializable"):
        await client.acreate_approval(function_name="tool", arguments={"x": value})
    assert requests == []


@pytest.mark.parametrize("value", NON_FINITE)
def test_oversight_rejects_non_finite_float(recorded, value):
    client, requests = recorded
    ran = []

    @oversight()
    def tool(x):
        ran.append(x)

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match=r"arguments\['x'\]\['n'\] is .*floats must be finite"),
    ):
        tool({"n": value})
    assert requests == []
    assert ran == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", NON_FINITE)
async def test_oversight_async_rejects_non_finite_float(recorded, value):
    client, requests = recorded

    @oversight()
    async def tool(x):
        pass

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match="floats must be finite"),
    ):
        await tool(value)
    assert requests == []


@pytest.mark.parametrize("value", NON_FINITE)
def test_crewai_gated_rejects_non_finite_float(recorded, value):
    client, requests = recorded
    wrapped = crewai.gated(lambda x: None, client=client)
    with pytest.raises(TypeError, match="JSON-serializable"):
        wrapped(x=value)
    assert requests == []


@pytest.mark.parametrize(
    ("payload", "type_name"),
    [
        pytest.param({1: "WIRE_100000", "1": "preview"}, "int", id="int-collides-with-str"),
        pytest.param({True: "v"}, "bool", id="bool"),
        pytest.param({None: "v"}, "NoneType", id="none"),
        pytest.param({1.5: "v"}, "float", id="float"),
    ],
)
def test_oversight_rejects_non_str_dict_key(recorded, payload, type_name):
    """A non-str key would be renamed in the approval payload while the
    function still receives the original key."""
    client, requests = recorded
    ran = []

    @oversight()
    def tool(payload):
        ran.append(payload)

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match=rf"key of type {type_name}; keys must be str"),
    ):
        tool(payload)
    assert requests == []
    assert ran == []


@pytest.mark.parametrize(
    ("payload", "type_name"),
    [
        pytest.param({1: "a"}, "int", id="non-str-key"),
        pytest.param({1: "a", "1": "b"}, "int", id="stringified-key-collision"),
        pytest.param({"nested": {True: "a"}}, "bool", id="nested-non-str-key"),
    ],
)
@pytest.mark.parametrize("entry_point", ["client", "crewai", "autogen", "oversight"])
def test_non_str_dict_key_parity(recorded, payload, type_name, entry_point):
    client, requests = recorded
    ran = []

    def tool(payload):
        ran.append(payload)

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match=rf"key of type {type_name}; keys must be str"),
    ):
        if entry_point == "client":
            client.create_approval(function_name="tool", arguments={"payload": payload})
        elif entry_point == "crewai":
            crewai.gated(tool, client=client)(payload=payload)
        elif entry_point == "autogen":
            autogen.gated(client=client)(tool)(payload=payload)
        else:
            oversight()(tool)(payload)
    assert requests == []
    assert ran == []


@pytest.mark.asyncio
@pytest.mark.parametrize("entry_point", ["client", "autogen", "oversight"])
async def test_async_non_str_dict_key_parity(recorded, entry_point):
    client, requests = recorded
    payload = {1: "a", "1": "b"}
    ran = []

    async def tool(payload):
        ran.append(payload)

    with (
        patch("sentinel.decorator.SentinelClient", return_value=client),
        pytest.raises(TypeError, match="key of type int; keys must be str"),
    ):
        if entry_point == "client":
            await client.acreate_approval(function_name="tool", arguments={"payload": payload})
        elif entry_point == "autogen":
            await autogen.gated(client=client)(tool)(payload=payload)
        else:
            await oversight()(tool)(payload)
    assert requests == []
    assert ran == []


def test_oversight_still_accepts_json_values(recorded):
    client, requests = recorded

    @oversight()
    def tool(a, b, c):
        return "ran"

    with patch("sentinel.decorator.SentinelClient", return_value=client):
        assert tool("s", (1, 2.5, None), {"k": [True]}) == "ran"
    assert requests[0].url.path == "/v1/approvals"
