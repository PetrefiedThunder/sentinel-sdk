class SentinelError(Exception):
    """Base error for the Sentinel SDK."""


class SentinelConfigError(SentinelError):
    """Raised when the SDK is used without required configuration."""


class ApprovalRejected(SentinelError):
    """Raised when an approval request is rejected by an approver."""

    def __init__(self, reason: str = "", action_id: str | None = None):
        self.reason = reason
        self.action_id = action_id
        super().__init__(reason or "Approval rejected")


class ApprovalTimeout(SentinelError):
    """Raised when an approval request times out without a decision."""

    def __init__(self, action_id: str | None = None, timeout_seconds: float | None = None):
        self.action_id = action_id
        self.timeout_seconds = timeout_seconds
        msg = f"Approval timed out after {timeout_seconds}s" if timeout_seconds else "Approval timed out"
        super().__init__(msg)
