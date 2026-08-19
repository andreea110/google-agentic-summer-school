"""Day 3 callbacks — SOLUTION."""

import time
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool
from google.genai import types


def log_tool_calls(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> Optional[dict]:
    """Prints every tool call to the terminal running `adk web`."""
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] 🔧 {tool_context.agent_name} → {tool.name}({args})")
    return None


REFUND_WORDS = ["refund", "money back", "chargeback", "rambursare"]

POLICY_ANSWER = (
    "I can't help with refunds or payments — that's handled by a human on the "
    "Playfield support team (support@playfield.example). I'm happy to help with "
    "anything about the games or their reviews!"
)


def refund_guardrail(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Blocks refund/payment requests before they ever reach the model."""
    last_user_text = ""
    for content in reversed(llm_request.contents or []):
        if content.role == "user" and content.parts and content.parts[0].text:
            last_user_text = content.parts[0].text
            break

    if any(word in last_user_text.lower() for word in REFUND_WORDS):
        callback_context.state["temp:refund_blocked"] = True
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=POLICY_ANSWER)])
        )
    return None
