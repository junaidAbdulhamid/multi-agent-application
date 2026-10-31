"""Model calls are kept in one place so the workflow remains easy to follow."""

import json
import os
from openai import OpenAI


def ask_json(instructions: str, context: dict) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running an AI job")
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        instructions=instructions + " Return only a JSON object, with no markdown.",
        input=json.dumps(context),
    )
    try:
        value = json.loads(response.output_text)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise RuntimeError("Model did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Model response must be a JSON object")
    return value
