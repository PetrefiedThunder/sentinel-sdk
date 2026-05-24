from unittest.mock import MagicMock, patch

import pytest

from sentinel import ApprovalRejected, oversight


@patch("sentinel.decorator.SentinelClient")
def test_approval_success(mock_client_cls):
    mock_client = MagicMock()
    mock_client.create_approval.return_value = {"action_id": "act_1"}
    mock_client.wait_for_decision.return_value = {"status": "approved"}
    mock_client_cls.return_value = mock_client

    @oversight(risk_level="high")
    def transfer_funds(amount, to):
        return {"amount": amount, "to": to}

    result = transfer_funds(100, to="alice")
    assert result == {"amount": 100, "to": "alice"}
    mock_client.create_approval.assert_called_once()
    mock_client.wait_for_decision.assert_called_once_with("act_1", timeout=None)
    mock_client.emit_audit_event.assert_called_once()


@patch("sentinel.decorator.SentinelClient")
def test_rejection(mock_client_cls):
    mock_client = MagicMock()
    mock_client.create_approval.return_value = {"action_id": "act_2"}
    mock_client.wait_for_decision.return_value = {
        "status": "rejected",
        "reason": "too risky",
    }
    mock_client_cls.return_value = mock_client

    ran = {"v": False}

    @oversight()
    def dangerous():
        ran["v"] = True
        return "done"

    with pytest.raises(ApprovalRejected) as exc:
        dangerous()
    assert "too risky" in str(exc.value)
    assert ran["v"] is False
