"""Day 4, Part 2 side-quest — AgentTool: an agent used AS a tool.

Two ways to compose agents:

1. WORKFLOW agents (SequentialAgent, ParallelAgent, LoopAgent) — YOU fix the
   control flow in code. Deterministic, predictable, debuggable. That's the
   main track today (playfield_report).

2. AgentTool — the MODEL decides. A whole agent is wrapped as a tool of
   another agent; the parent calls it like any function when it judges it
   needs to. Flexible, and exactly as (un)predictable as any tool choice.

This demo is option 2: a concierge that can answer small questions itself but
delegates review-research to a wrapped specialist. Watch the Events tab: the
specialist's run appears nested inside the parent's tool call.

Rule of thumb: fixed process → workflow agents; open-ended routing → AgentTool.
"""

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool

from playfield_report import tools

load_dotenv(tools.repo_root() / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"

review_specialist = LlmAgent(
    name="review_specialist",
    model=MODEL,
    description=(
        "Answers questions about what Playfield players say, feel, or complain "
        "about, backed by review search. Give it one clear question."
    ),
    instruction="""Research the question you are given using search_reviews
(2-3 different queries), then answer in a short paragraph citing review ids.""",
    tools=[tools.search_reviews],
)

root_agent = LlmAgent(
    name="playfield_concierge",
    model=MODEL,
    description="Front desk for Playfield questions.",
    instruction="""You are Playfield's concierge.

- Catalog facts (price, year, developer, ratings): answer yourself with
  list_games / get_game_details.
- Anything about player OPINIONS or experiences: delegate to the
  review_specialist tool with one clear, self-contained question.
- Combine what comes back into a friendly answer.""",
    tools=[
        tools.list_games,
        tools.get_game_details,
        AgentTool(agent=review_specialist),
    ],
)
