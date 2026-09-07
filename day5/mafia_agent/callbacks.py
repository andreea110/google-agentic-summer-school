"""Day 5, Part 3 — the token callback (step 3.3).

join_game returns your secret token, and every later tool call needs it.
Right now the token lives ONLY in the conversation history — if the model
drops or garbles it (long games, long contexts…), your player is locked out
of its own game.

The fix is Day 3's lesson: important state is EXPLICIT state. An
after_tool_callback fires after every tool call, sees the tool's result,
and can write to session state — the perfect place to catch the token the
moment join_game returns it.
"""

import json
from typing import Any, Optional

from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool

TOKEN_KEY = "game:token"


def _find_token(payload: Any) -> Optional[str]:
    """Dig the token out of whatever shape the MCP layer hands us.

    join_game returns a plain {"token": ...} dict server-side, but it travels
    through MCP before it reaches us: depending on the transport it can arrive
    already parsed, wrapped in a "result"/"structuredContent" envelope, or as
    a content list holding the JSON as text. Rather than betting on one shape,
    walk the structure and take the first "token" we meet.
    """
    if isinstance(payload, dict):
        token = payload.get("token")
        if isinstance(token, str) and token:
            return token
        for value in payload.values():
            found = _find_token(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_token(item)
            if found:
                return found
    elif isinstance(payload, str):
        # A content part carrying the tool's JSON as text.
        try:
            return _find_token(json.loads(payload))
        except (ValueError, TypeError):
            return None
    return None


def save_token(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> Optional[dict]:
    """After join_game succeeds, stash the token in session state.

    Return None so the tool result flows through unchanged — this callback
    observes, it doesn't rewrite.
    """
    if tool.name != "join_game":
        return None  # not our business

    token = _find_token(tool_response)
    if not token:
        # join_game can legitimately fail (duplicate name, table full): the
        # server answers {"error": ...} and there is simply no token to save.
        print(f"⚠️  join_game returned no token: {tool_response}")
        return None

    tool_context.state[TOKEN_KEY] = token
    print(f"🔐 token saved to state['{TOKEN_KEY}'] (…{token[-4:]})")
    return None
