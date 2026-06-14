"""Regression test for 0.1.8 — fail fast on un-serializable arguments."""

import pytest

from sentinel.client import _ensure_json_serializable


def test_plain_dict_ok():
    _ensure_json_serializable({"amount": 100, "recipient": "alice"})


def test_nested_dict_ok():
    _ensure_json_serializable({"meta": {"tags": ["a", "b"], "n": 1}})


def test_primitives_ok():
    for v in (None, True, 1, 1.5, "str", [], {}, [1, 2, 3]):
        _ensure_json_serializable(v)


def test_set_raises_typeerror():
    with pytest.raises(TypeError, match="JSON-serializable"):
        _ensure_json_serializable({1, 2, 3})


def test_bytes_raises_typeerror():
    with pytest.raises(TypeError, match="JSON-serializable"):
        _ensure_json_serializable(b"bytes")


def test_object_raises_typeerror():
    class Foo:
        pass

    with pytest.raises(TypeError, match="JSON-serializable"):
        _ensure_json_serializable(Foo())


def test_nested_unserializable_raises():
    with pytest.raises(TypeError, match="JSON-serializable"):
        _ensure_json_serializable({"ok": "yes", "bad": {1, 2}})
