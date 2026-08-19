"""Day 4 · Multi-agent systems — SOLUTION (end-of-day state).

    [reviews researcher ∥ docs researcher] ─▶ writer ─▶ (critic ⇄ reviser) ×≤3

Note: §4.1 first builds the critic with a prose protocol (reply exactly
"REPORT APPROVED"); §4.3 retires that magic string in favor of the typed
CritiqueVerdict below. This file shows the final, typed state.
"""

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from pydantic import BaseModel, Field

from . import tools

load_dotenv(tools.repo_root() / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"


# --------------------------------------------------------------------------
# Stage 1 — parallel research
# --------------------------------------------------------------------------

reviews_researcher = LlmAgent(
    name="reviews_researcher",
    model=MODEL,
    description="Researches player sentiment in the review corpus.",
    instruction="""You are a research specialist for Playfield. The user message
contains a research question about one or more Playfield games.

Call search_reviews 2 to 4 times with DIFFERENT, specific queries that cover the
question from several angles (e.g. technical problems, value for money, praise,
comparisons). If you need a game's catalog stats, call get_game_details.

Then output your findings as concise bullet points:
- one bullet per distinct theme you found,
- each bullet ends with the supporting review ids, e.g. (r042, r187),
- note whether the reviewers recommend the game or not.

Facts only. No recommendations, no report — that is another agent's job.""",
    tools=[tools.search_reviews, tools.get_game_details, tools.list_games],
    output_key="reviews_findings",
)

docs_researcher = LlmAgent(
    name="docs_researcher",
    model=MODEL,
    description="Researches the official docs: store pages and patch notes.",
    instruction="""You are a documentation specialist for Playfield. The user
message contains a research question that mentions one or more Playfield games.

Your job is NOT to answer the question — it is to assemble the OFFICIAL RECORD
of the game(s) it mentions, so a later agent can answer. Even if the question
is about strategy or opinion, the official record is still your assignment.

ALWAYS call search_docs, 1 to 3 times, with specific queries about the game(s):
patch notes, store page, features, what the developers shipped, fixed, or
changed — and WHEN.

Then output your findings as concise bullet points:
- facts only, each with its source file and any dates, e.g.
  "v1.2 fixed save corruption, 2026-01-15 (g12-patch-notes.md)".
- If the docs don't cover something the question needs, say so explicitly —
  after searching, never instead of searching.

No opinions, no recommendations — that is another agent's job.""",
    tools=[tools.search_docs],
    output_key="docs_findings",
)

research_team = ParallelAgent(
    name="research_team",
    sub_agents=[reviews_researcher, docs_researcher],
)


# --------------------------------------------------------------------------
# Stage 2 — the writer
# --------------------------------------------------------------------------

writer = LlmAgent(
    name="report_writer",
    model=MODEL,
    description="Writes the final report from the researchers' findings.",
    instruction="""Write a decision report answering the user's research question,
using ONLY the findings below. Do not invent evidence.

PLAYER RESEARCH:
{reviews_findings}

OFFICIAL DOCS RESEARCH:
{docs_findings}

Use exactly this structure (markdown):

## Question
Restate the question in one sentence.

## What players say
The main themes from reviews, with review ids as citations.

## What the docs say
The relevant facts from store pages / patch notes, with file names and dates.

## Timeline check
Where player complaints and official fixes interact: were the complaints
before or after the fix? Is the criticism still current?

## Verdict
A clear, actionable recommendation (2-4 sentences), with an explicit
confidence level (high / medium / low) and what evidence would change it.

Keep the whole report under 400 words.""",
    output_key="report_draft",
)


# --------------------------------------------------------------------------
# Stage 3 — the quality loop (§4.3: typed verdict, no magic strings)
# --------------------------------------------------------------------------


class CritiqueVerdict(BaseModel):
    """The critic's checklist, as data instead of prose."""

    review_citations_ok: bool = Field(
        description="Every claim about player opinion cites review ids like (r042)."
    )
    doc_citations_ok: bool = Field(
        description="Every claim about fixes/updates cites a doc file and, where relevant, a date."
    )
    sections_ok: bool = Field(
        description="All five sections are present: Question, What players say, "
        "What the docs say, Timeline check, Verdict."
    )
    verdict_ok: bool = Field(
        description="The Verdict is actionable and states a confidence level."
    )
    length_ok: bool = Field(
        description="The report is under 400 words and contains no invented evidence."
    )
    passed: bool = Field(
        description="True ONLY if every other check above is true."
    )
    fixes: list[str] = Field(
        description="The specific, actionable problems to fix. Empty when passed."
    )


critic = LlmAgent(
    name="report_critic",
    model=MODEL,
    description="Checks the report draft against the quality bar.",
    include_contents="none",
    instruction="""You are a meticulous editor. Review this report draft:

```
{report_draft}
```

Assess it honestly against every check in the verdict schema. Set `passed`
to true ONLY if all five checks pass; otherwise list the specific problems
in `fixes` — each one concrete enough that a reviser can act on it.""",
    output_schema=CritiqueVerdict,
    output_key="critique",
)

reviser = LlmAgent(
    name="report_reviser",
    model=MODEL,
    description="Applies the critique, or approves and exits the loop.",
    include_contents="none",
    instruction="""You maintain a report draft.

CURRENT DRAFT:
```
{report_draft}
```

EDITOR'S VERDICT (a JSON object):
{critique}

If "passed" is true: call the exit_loop function. Do not output any text.

Otherwise: rewrite the draft, fixing every item in "fixes", keeping the same
five-section structure. Output ONLY the revised report.""",
    tools=[tools.exit_loop],
    output_key="report_draft",
)

quality_loop = LoopAgent(
    name="quality_loop",
    sub_agents=[critic, reviser],
    max_iterations=3,
)


# --------------------------------------------------------------------------
# The pipeline
# --------------------------------------------------------------------------

root_agent = SequentialAgent(
    name="report_pipeline",
    description="Researches a question about Playfield games and produces a structured report.",
    sub_agents=[research_team, writer, quality_loop],
)
