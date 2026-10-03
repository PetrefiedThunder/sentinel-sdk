"""Offline checks of the README's onboarding and public configuration contract."""

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import sentinel
import sentinel.config as config_module
from sentinel import ApprovalRejected, SentinelClient, SentinelConfig, SentinelConfigError


@pytest.fixture
def isolated_config(monkeypatch):
    config = SentinelConfig(
        api_url="https://qa.invalid",
        api_key=None,
        timeout_seconds=300,
        poll_interval=2,
        fallback="reject",
    )
    monkeypatch.setattr(config_module, "_config", config)
    return config


@pytest.fixture
def quickstart(monkeypatch, isolated_config):
    """Run the actual first Python fence, without approval or payment network calls."""
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    source = re.findall(r"```python\n(.*?)```", readme, flags=re.DOTALL)[0]
    client = MagicMock(spec=SentinelClient)
    client.create_approval.return_value = {"action_id": "qa-action"}
    client.wait_for_decision.return_value = {"status": "approved"}
    monkeypatch.setattr("sentinel.decorator.SentinelClient", lambda config: client)
    monkeypatch.setattr(sentinel, "configure", MagicMock())
    namespace = {}
    exec(compile(source, "README.md:29", "exec"), namespace)
    return namespace, client


@pytest.mark.xfail(
    strict=True,
    raises=NameError,
    reason="UX-002: README quickstart invokes stripe without importing or supplying it",
)
def test_readme_quickstart_runs_after_approval(quickstart):
    namespace, _ = quickstart
    namespace["transfer_funds"](1000, "acct_qa")


def test_readme_quickstart_passes_when_missing_payment_symbol_is_supplied(quickstart):
    namespace, client = quickstart
    transfer = MagicMock(return_value={"id": "qa-transfer"})
    namespace["stripe"] = SimpleNamespace(transfers=SimpleNamespace(create=transfer))
    assert namespace["transfer_funds"](1000, "acct_qa") == {"id": "qa-transfer"}
    transfer.assert_called_once_with(amount=1000, destination="acct_qa")
    assert client.create_approval.call_args.kwargs["arguments"] == {
        "amount": 1000,
        "recipient": "acct_qa",
    }


def test_readme_quickstart_rejection_exposes_reason_and_prevents_payment(quickstart):
    namespace, client = quickstart
    client.wait_for_decision.return_value = {"status": "rejected", "reason": "Needs review"}
    transfer = MagicMock()
    namespace["stripe"] = SimpleNamespace(transfers=SimpleNamespace(create=transfer))
    with pytest.raises(ApprovalRejected, match="Needs review") as error:
        namespace["transfer_funds"](1000, "acct_qa")
    assert error.value.action_id == "qa-action"
    transfer.assert_not_called()


@pytest.mark.parametrize(
    ("env_name", "env_value", "attribute", "expected"),
    [
        ("SENTINEL_API_URL", "https://qa.invalid", "api_url", "https://qa.invalid"),
        ("SENTINEL_API_KEY", "qa-placeholder", "api_key", "qa-placeholder"),
        ("SENTINEL_TIMEOUT", "17.5", "timeout_seconds", 17.5),
        ("SENTINEL_FALLBACK", "execute", "fallback", "execute"),
        pytest.param(
            "SENTINEL_POLL_INTERVAL",
            "0.25",
            "poll_interval",
            0.25,
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="UX-001: documented SENTINEL_POLL_INTERVAL environment variable is ignored",
            ),
        ),
    ],
)
def test_readme_environment_configuration(monkeypatch, env_name, env_value, attribute, expected):
    for variable in (
        "SENTINEL_API_URL",
        "SENTINEL_API_KEY",
        "SENTINEL_TIMEOUT",
        "SENTINEL_FALLBACK",
        "SENTINEL_POLL_INTERVAL",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(env_name, env_value)
    assert getattr(SentinelConfig(), attribute) == expected


def test_configure_preserves_fields_when_setting_one_option(isolated_config):
    configured = sentinel.configure(poll_interval=0.25)
    assert sentinel.get_config() is configured
    assert configured.poll_interval == 0.25
    assert configured.api_url == isolated_config.api_url
    assert configured.timeout_seconds == isolated_config.timeout_seconds


def test_missing_configuration_explains_recovery_before_network(monkeypatch, isolated_config):
    constructor = MagicMock(side_effect=AssertionError("HTTP client must not be created"))
    monkeypatch.setattr("sentinel.client.httpx.Client", constructor)
    with pytest.raises(SentinelConfigError, match=r"sentinel\.configure\(api_key="):
        SentinelClient().get_tenant()
    constructor.assert_not_called()


def test_oversight_preserves_discoverable_function_signature():
    import inspect

    @sentinel.oversight()
    def action(amount: int, recipient: str = "qa-recipient") -> str:
        """Example operation visible to Python help and agent frameworks."""
        return recipient

    assert action.__name__ == "action"
    assert action.__doc__ == "Example operation visible to Python help and agent frameworks."
    assert list(inspect.signature(action).parameters) == ["amount", "recipient"]


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="UX-003: missing required function argument requests approval before raising TypeError",
)
def test_missing_required_argument_fails_before_requesting_human_approval(quickstart):
    namespace, client = quickstart
    with pytest.raises(TypeError, match="required positional argument"):
        namespace["transfer_funds"](1000)
    client.create_approval.assert_not_called()
