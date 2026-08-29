import json
from types import SimpleNamespace

import pytest

from guardcode import model


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=FakeCompletions(response))


def make_response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def test_call_model_returns_text_and_sends_registered_tools(monkeypatch):
    fake_client = FakeClient(make_response(content="Done"))
    monkeypatch.setattr(model, "OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(model, "get_tool_schemas", lambda: [{"type": "function"}])

    result = model.call_model(
        [{"role": "user", "content": "hello"}],
        model_name="custom-model",
        api_key="test-key",
        api_base="https://example.test/v1",
    )

    assert result == {"content": "Done", "tool_calls": []}
    assert fake_client.chat.completions.kwargs == {
        "model": "custom-model",
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function"}],
    }


def test_call_model_parses_tool_calls_into_standard_dicts(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="read_file", arguments=json.dumps({"path": "a.py"})),
    )
    fake_client = FakeClient(make_response(tool_calls=[tool_call]))
    monkeypatch.setattr(model, "OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(model, "get_tool_schemas", lambda: [])

    result = model.call_model([{"role": "user", "content": "read it"}], api_key="test-key")

    assert result == {
        "content": None,
        "tool_calls": [
            {"id": "call-1", "name": "read_file", "arguments": {"path": "a.py"}}
        ],
    }


def test_call_model_reads_environment_defaults(monkeypatch):
    fake_client = FakeClient(make_response(content="ok"))
    captured = {}

    def create_client(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(model, "OpenAI", create_client)
    monkeypatch.setattr(model, "get_tool_schemas", lambda: [])
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://compatible.test/v1")
    monkeypatch.setenv("GUARDCODE_MODEL", "env-model")

    model.call_model([])

    assert captured == {"api_key": "env-key", "base_url": "https://compatible.test/v1"}
    assert fake_client.chat.completions.kwargs["model"] == "env-model"


def test_call_model_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        model.call_model([])


def test_call_model_rejects_empty_response(monkeypatch):
    fake_client = FakeClient(SimpleNamespace(choices=[]))
    monkeypatch.setattr(model, "OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(model, "get_tool_schemas", lambda: [])

    with pytest.raises(RuntimeError, match="no choices"):
        model.call_model([], api_key="test-key")


def test_call_model_rejects_invalid_tool_arguments(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="read_file", arguments="not-json"),
    )
    fake_client = FakeClient(make_response(tool_calls=[tool_call]))
    monkeypatch.setattr(model, "OpenAI", lambda **kwargs: fake_client)
    monkeypatch.setattr(model, "get_tool_schemas", lambda: [])

    with pytest.raises(ValueError, match="call-1"):
        model.call_model([], api_key="test-key")
