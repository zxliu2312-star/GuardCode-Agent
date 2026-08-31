"""OpenAI-compatible Chat Completions model adapter."""

import json
import os
from typing import Any

from openai import OpenAI

from .tools.base import get_tool_schemas

DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4-turbo"


def _resolve_setting(
    value: str | None,
    environment_name: str,
    default: str | None = None,
) -> str | None:
    if value is not None:
        return value
    return os.getenv(environment_name, default)


def _parse_tool_calls(tool_calls: list[Any] | None) -> list[dict[str, Any]]:
    parsed_calls = []
    for tool_call in tool_calls or []:
        try:
            arguments = json.loads(tool_call.function.arguments)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"Invalid arguments for tool call {tool_call.id}: {error}"
            ) from error

        if not isinstance(arguments, dict):
            raise ValueError(
                f"Invalid arguments for tool call {tool_call.id}: expected a JSON object"
            )

        parsed_calls.append(
            {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": arguments,
            }
        )
    return parsed_calls


def call_model(
    messages: list[dict[str, Any]],
    model_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> dict[str, Any]:
    """Call an OpenAI-compatible Chat Completions endpoint.

    Returns a provider-independent response containing assistant text and parsed
    local tool calls. API errors are allowed to propagate to the caller so the
    agent loop can decide how to report or retry them.
    """
    resolved_api_key = _resolve_setting(api_key, "OPENAI_API_KEY")
    if not resolved_api_key:
        raise ValueError("OPENAI_API_KEY is required to call the model")

    resolved_api_base = _resolve_setting(api_base, "OPENAI_API_BASE", DEFAULT_API_BASE)
    resolved_model = _resolve_setting(model_name, "GUARDCODE_MODEL", DEFAULT_MODEL)

    client = OpenAI(api_key=resolved_api_key, base_url=resolved_api_base)
    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        tools=get_tool_schemas(),
    )

    if not response.choices:
        raise RuntimeError("Model response contains no choices")

    message = response.choices[0].message
    return {
        "content": message.content,
        "tool_calls": _parse_tool_calls(message.tool_calls),
        "finish_reason": response.choices[0].finish_reason,
    }
