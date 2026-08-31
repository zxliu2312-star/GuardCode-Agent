"""OpenAI-compatible Chat Completions model adapter.

Provides call_model() for single calls and call_model_with_retry()
for automatic retry with exponential backoff on transient failures.
"""

import json
import os
import time
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


def call_model_with_retry(
    messages: list[dict[str, Any]],
    model_name: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Call the model with automatic retry on transient failures.

    Uses exponential backoff: wait 2^attempt seconds between retries.
    Catches network errors and API errors (rate limits, server errors).
    After max_retries failed attempts, the last exception is re-raised.

    Args:
        messages: Message list to send
        model_name: Model name override
        api_key: API key override
        api_base: API base URL override
        max_retries: Maximum retry attempts (default 3)

    Returns:
        Model response dict (same as call_model)

    Raises:
        Exception: The last error if all retries fail
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return call_model(
                messages,
                model_name=model_name,
                api_key=api_key,
                api_base=api_base,
            )
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s, ...
                # Log retry attempt
                try:
                    from .ui.console import get_logger
                    get_logger().warning(
                        f"Model call failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                except Exception:
                    pass
                time.sleep(wait_time)

    # All retries exhausted
    raise last_error  # type: ignore[misc]
