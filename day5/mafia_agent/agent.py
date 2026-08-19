"""Day 5, Parts 3–4 — your player for Agentic Mafia.

This is a STARTER, not a solution: it knows the rules and it plays legally.
It also plays terribly. The tournament is won in two places, both yours:

- STRATEGY (below): how your agent talks, whom it suspects, when it lies.
- Architecture: one agent reading raw scrollback, or something smarter —
  a notes ledger in state, a critic sub-agent that vets your public message
  before it's sent, a per-opponent suspicion model… (Day 4 was practice.)

The game server is an MCP server (Day 3's third kind of tool): every rule
is enforced server-side, so all agents play the exact same game — the only
variable is how well yours thinks.

Point MAFIA_SERVER_URL at the instructor's machine, e.g.
    export MAFIA_SERVER_URL="http://192.168.1.50:8000/mcp"
then either chat with your player in `adk web` ("join as <your name> and
play") or let it play by itself:  python -m mafia_agent.play --name <name>
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from . import callbacks  # noqa: F401  (used in the Part-3 exercise below)

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"
SERVER_URL = os.environ.get("MAFIA_SERVER_URL", "http://localhost:8000/mcp")

game_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=SERVER_URL,
        timeout=60,  # `next` long-polls for up to ~20s — give it room
        sse_read_timeout=120,
    ),
)

GAME_RULES = """You are a player in Agentic Mafia, a social deduction
game. All players are AI agents; the game server enforces every rule.

THE SETUP: each player is secretly a KILLER (a team — they know each other),
a HEALER, or a CIVILIAN. The killers win when they equal or outnumber
everyone else. Everyone else wins when all killers are dead.

EACH ROUND:
1. TALK — every living player submits exactly ONE public message
   (max 300 chars). All messages are revealed at the same time. There is
   NO back-and-forth within a round: a question you ask can only be
   answered at the NEXT round's reveal, so write a complete, self-contained
   statement, not a conversation opener.
2. ACT — after reading the chat, everyone secretly votes to lynch someone
   (plurality wins; a tie means nobody dies; "" abstains). Votes are
   SECRET: nobody ever sees who voted for whom, only the dawn outcome,
   so what players DECLARE in chat is the only vote signal that exists. Killers also
   pick a victim; the healer also picks someone to protect (self allowed,
   a heal blocks the kill, never the vote). EXCEPTION: there is NO lynch
   vote in round 1: the first night, leave vote empty.
3. DAWN — deaths are announced with causes; a blocked kill is announced
   without naming who was saved. A dead player's role is revealed ONLY if
   a dawn line states it explicitly — otherwise it stays unknown. Then a
   new round begins.

HOW TO PLAY, MECHANICALLY:
- join_game once, with the player name the user gives you. It returns your
  secret token — every other tool needs it. NEVER write the token in chat.
- Then loop forever: call next, read the state, and do exactly what its
  to_do field says (send_message, submit_action, or just call next again).
- next only shows the CURRENT round's chat. Anything worth remembering
  from earlier rounds, you must carry yourself.
- If a tool returns {"error": ...}, read it, fix your call, and continue.
- When the state says game_over, report the result and stop."""

# TODO(you): Part 3 — this is the whole assignment. Replace this with a real
# strategy: how do you avoid suspicion as a killer? how do you smoke out
# killers as a civilian? whom does the healer protect? what do you say, and
# what do you NEVER say?
STRATEGY = """STRATEGY: be sensible. Vote for whoever seems most suspicious;
as a killer, don't kill a teammate; as the healer, protect whoever the
killers most likely want dead. Keep messages short and unremarkable."""

root_agent = LlmAgent(
    model=MODEL,
    name="mafia_player",
    description="Plays Agentic Mafia against the class via MCP.",
    instruction=GAME_RULES + "\n\n" + STRATEGY,
    tools=[game_tools],
    # Part 3 (step 3.3): tokens shouldn't live only in fragile chat history.
    #   after_tool_callback=callbacks.save_token
)
