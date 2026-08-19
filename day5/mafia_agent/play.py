"""Run your player autonomously — no chat window, no human in the loop.

    cd day5
    python -m mafia_agent.play --name <your-unique-name>

`adk web` is great for poking at your player, but a tournament needs the
agent to drive ITSELF: this script gives the model one standing order
("play"), lets it chain tool calls freely, and nudges it again whenever it
stops to talk — until the game is over. That outer while-loop is the whole
trick behind every "autonomous" agent you've met this week.
"""

from __future__ import annotations

import argparse
import asyncio

from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import SERVER_URL, root_agent

KICKOFF = (
    "Join the game as {name!r} and play it to the end. Follow every to_do. "
    "After each round, state in ONE short line what you did and why (do not "
    "reveal your token). When the game is over, say GAME OVER and the result."
)
NUDGE = (
    "Continue playing: call next and follow its to_do. If the game has "
    "ended, say GAME OVER and the result."
)


def show(event) -> None:
    """One compact line per model step — your player's play-by-play."""
    if not event.content:
        return
    for part in event.content.parts or []:
        if part.function_call:
            args = {k: v for k, v in (part.function_call.args or {}).items()}
            if "token" in args:
                args["token"] = "…"  # never print secrets, even locally
            print(f"  🔧 {part.function_call.name}({args})")
        elif part.text and part.text.strip():
            print(f"  🗣️  {part.text.strip()}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="autonomous Mafia player")
    parser.add_argument("--name", required=True, help="your unique player name")
    parser.add_argument(
        "--max-turns", type=int, default=60,
        help="safety cap on nudges — a bounded loop, as always (Day 4)")
    args = parser.parse_args()

    print(f"🎭 {args.name} connecting to {SERVER_URL}")
    runner = InMemoryRunner(agent=root_agent, app_name="mafia")
    await runner.session_service.create_session(
        app_name="killer", user_id=args.name, session_id="game")

    message = KICKOFF.format(name=args.name)
    for turn in range(args.max_turns):
        final_text = ""
        async for event in runner.run_async(
            user_id=args.name,
            session_id="game",
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        ):
            show(event)
            if event.content and event.content.parts:
                final_text = "".join(p.text or "" for p in event.content.parts)
        if "GAME OVER" in final_text.upper():
            print("🏁 done.")
            return
        message = NUDGE
    print("⏱️ max turns reached — stopping (is the server still up?)")


if __name__ == "__main__":
    asyncio.run(main())
