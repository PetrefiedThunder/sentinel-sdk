"""Keep the QA suite offline even if a test accidentally omits its HTTP mock."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_test_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("QA tests must use local stubs or httpx.MockTransport")

    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
