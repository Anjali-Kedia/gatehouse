"""Unit tests for GroqAdapter's response parsing — mocked, no network calls.
These exercise error paths (malformed JSON, an out-of-enum choice) that are
impractical to trigger reliably against the real API on demand.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import openai
import pytest

from gatehouse.jev.base import JevUnavailable
from gatehouse.jev.groq import GroqAdapter
from gatehouse.reason_codes import ReasonCode


def _fake_response(arguments_json: str) -> SimpleNamespace:
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=arguments_json))
    message = SimpleNamespace(tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    return SimpleNamespace(choices=[choice], model="fake-model", usage=usage)


def _adapter_with_fake_client(response) -> GroqAdapter:
    adapter = GroqAdapter.__new__(GroqAdapter)  # skip __init__'s API-key requirement
    adapter._client = MagicMock()
    adapter._client.chat.completions.create.return_value = response
    return adapter


def test_valid_response_is_parsed_correctly():
    args = json.dumps(
        {
            "match": {"choice": "matches", "confidence": 0.9},
            "explicit": {"choice": "explicit", "confidence": 0.8},
            "specific": {"choice": "sufficient", "confidence": 0.7},
        }
    )
    adapter = _adapter_with_fake_client(_fake_response(args))
    result = adapter.evaluate(user_request="x", proposed_tool="get_order", proposed_arguments={}, context={})

    assert result.match.choice == "matches"
    assert result.match.confidence == 0.9
    assert result.usage == {"input_tokens": 100, "output_tokens": 50}


def test_out_of_enum_choice_raises_jev_unavailable():
    args = json.dumps(
        {
            "match": {"choice": "definitely_not_a_real_option", "confidence": 0.9},
            "explicit": {"choice": "explicit", "confidence": 0.8},
            "specific": {"choice": "sufficient", "confidence": 0.7},
        }
    )
    adapter = _adapter_with_fake_client(_fake_response(args))

    with pytest.raises(JevUnavailable) as exc_info:
        adapter.evaluate(user_request="x", proposed_tool="get_order", proposed_arguments={}, context={})
    assert exc_info.value.reason_code == ReasonCode.JEV_INVALID_RESPONSE


def test_malformed_json_raises_jev_unavailable():
    adapter = _adapter_with_fake_client(_fake_response('{"match": {"choice": "matches", "confidence": 0.9'))

    with pytest.raises(JevUnavailable) as exc_info:
        adapter.evaluate(user_request="x", proposed_tool="get_order", proposed_arguments={}, context={})
    assert exc_info.value.reason_code == ReasonCode.JEV_INVALID_RESPONSE


def test_api_error_raises_jev_unavailable():
    adapter = GroqAdapter.__new__(GroqAdapter)
    adapter._client = MagicMock()
    adapter._client.chat.completions.create.side_effect = openai.APIConnectionError(request=MagicMock())

    with pytest.raises(JevUnavailable) as exc_info:
        adapter.evaluate(user_request="x", proposed_tool="get_order", proposed_arguments={}, context={})
    assert exc_info.value.reason_code == ReasonCode.JEV_UNAVAILABLE
