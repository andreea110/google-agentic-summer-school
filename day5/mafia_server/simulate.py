"""Scripted bot players for Agentic Mafia — no LLM involved.

Two jobs:

- **Smoke test**: `python -m mafia_server.simulate --players 5` plays a full
  game against a running server and prints the outcome (instructors: run this
  the evening before).
- **Seat filler**: students absent? `--players 2 --prefix filler` tops up a
  table with random-but-legal players so a game can start.

The bots follow exactly the loop the students' agents follow (join → next →
send_message → next → submit_action → next …), but pick targets randomly and
talk in canned phrases — a floor, not a bar. Any student agent that reasons
about the chat should beat them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SMALL_TALK = [
    "I trust no one, but especially not whoever speaks next.",
    "I'm just a simple villager who definitely slept all night.",
    "Someone here is lying. Statistically speaking.",
    "I saw nothing, I know nothing, I vote on vibes.",
    "If I die tonight, avenge me. Or don't. I'm a bot.",
    "The quiet ones are always suspicious.",
    "Killer, preda-te! (Worth a try.)",
]


async def call(session: ClientSession, tool: str, **args) -> dict:
    result = await session.call_tool(tool, args)
    return json.loads(result.content[0].text)


async def play(url: str, name: str, verbose: bool) -> str:
    rng = random.Random(name)
    async with streamablehttp_client(url, timeout=60, sse_read_timeout=120) as (
        read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            joined = await call(session, "join_game", player_name=name)
            if "error" in joined:
                return f"{name}: could not join — {joined['error']}"
            token = joined["token"]
            role = None
            while True:
                state = await call(session, "next", token=token)
                if "error" in state:
                    return f"{name}: {state['error']}"
                role = state.get("you", {}).get("role", role)
                status = state["status"]
                if status == "game_over":
                    return f"{name} ({role}): game over — {state['winner']} win(s)"
                if status in ("lobby", "waiting", "dead"):
                    continue
                phase, this_round = state["phase"], state["round"]
                me, others = state["you"]["name"], [
                    p for p in state["players_alive"]
                    if p != state["you"]["name"]]
                if phase == "talk" and "ONE public message" in state["to_do"]:
                    msg = rng.choice(SMALL_TALK)
                    await call(session, "send_message", token=token, message=msg)
                    if verbose:
                        print(f"  r{this_round} 💬 {name}: {msg}")
                elif phase == "act" and "submit_action" in state["to_do"]:
                    partners = state["you"].get("your_fellow_killers", [])
                    # no lynch on the first night — the server rejects votes
                    can_vote = this_round > 1
                    action = {"vote": rng.choice(others + [""]) if can_vote else ""}
                    if role == "killer":
                        prey = [p for p in others if p not in partners]
                        action["kill_target"] = rng.choice(prey or others)
                    elif role == "healer":
                        action["heal_target"] = rng.choice([me] + others)
                    await call(session, "submit_action", token=token, **action)
                    if verbose:
                        print(f"  r{this_round} 🎯 {name} ({role}): {action}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="scripted Killer players")
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    parser.add_argument("--players", type=int, default=5)
    parser.add_argument("--prefix", default="bot")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    names = [f"{args.prefix}-{i + 1}" for i in range(args.players)]
    print(f"🤖 {len(names)} bots joining {args.url} — start the table from the "
          "dashboard when ready.")
    results = await asyncio.gather(
        *(play(args.url, name, verbose=not args.quiet) for name in names),
        return_exceptions=True)
    for name, res in zip(names, results):
        print(f"  {res if not isinstance(res, Exception) else f'{name}: {res!r}'}")


if __name__ == "__main__":
    asyncio.run(main())
