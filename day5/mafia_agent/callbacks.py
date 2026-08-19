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

from typing import Any, Optional

from google.adk.tools import ToolContext
from google.adk.tools.base_tool import BaseTool


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
    # TODO(you): Part 3, step 3.3
    #   1. if tool.name != "join_game", return None (not our business)
    #   2. the MCP tool result arrives as a dict — find the token in
    #      tool_response (print it once to see the exact shape!)
    #   3. if there is one: tool_context.state["game:token"] = <token>
    #      and print a confirmation to the terminal
    #   4. return None
    #
    # Then wire it up in agent.py (after_tool_callback=callbacks.save_token)
    # and add this line to the end of GAME_RULES so the model can always see
    # the saved value:  "Your saved token (if any): {game:token?}"
    raise NotImplementedError("Part 3, step 3.3")
