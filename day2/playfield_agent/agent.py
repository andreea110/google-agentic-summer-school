"""Day 2 · Your first agent — scaffold.

You edit this file in every part of the walkthrough. Restart `adk web` is NOT
needed after edits — it reloads agents on refresh.
"""

from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from . import tools

load_dotenv(tools.repo_root() / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"

root_agent = LlmAgent(
    model=MODEL,
    name="playfield_analyst",
    description="Data analyst for the Playfield game storefront.",
    # Part 1: run it exactly like this — no tools, minimal instruction.
    # Part 4: you will rewrite this instruction properly (step 4.1).
    instruction="You are a helpful assistant for the Playfield game storefront.",
    # Part 2 (step 2.1): add tools.list_games and tools.get_game_details.
    # Part 3 (step 3.3): add tools.search_reviews and tools.analyze_review.
    tools=[
        tools.list_games,
        tools.get_game_details,
        tools.search_reviews,
        tools.analyze_review,
    ],
)
