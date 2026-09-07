"""Day 4 · Multi-agent systems — scaffold.

You build the report pipeline in stages. Part 1 already works: run it first,
then upgrade it part by part.

    Part 1 (works now):  researcher ──▶ writer
    Part 2 (you build):  [reviews researcher ∥ docs researcher] ──▶ writer
    Part 3 (you build):  … ──▶ writer with the full report template
    Part 4 (you build):  … ──▶ writer ──▶ (critic ⇄ reviser) loop
"""

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from pydantic import BaseModel, Field

from . import tools

load_dotenv(tools.repo_root() / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"


# --------------------------------------------------------------------------
# Part 1 — a two-stage pipeline (provided, working)
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
    description="Researches the official record: store pages and dated patch notes.",
    instruction="""You are a documentation specialist for Playfield. The user
message contains a research question about one or more Playfield games.

Your job is NOT to answer the question. Your job is to establish the OFFICIAL
RECORD of every game the question mentions: what the developers shipped, fixed,
or changed, and when.

Call search_docs 2 to 4 times with DIFFERENT, specific queries. Cover at least:
- known problems and their fixes ("save corruption fix", "performance patch"),
- features and requirements from the store page.

You may only report that something is not documented AFTER you have searched.
Never answer "the docs don't cover this" without at least two searches first.

Then output your findings as concise bullet points. Every bullet must carry a
fact, a date, and the source file, e.g.:
- v1.2 fixed save corruption, 2026-01-15 (g12-patch-notes.md)

Facts only. No opinions, no recommendations, no report — that is another
agent's job.""",
    tools=[tools.search_docs],
    output_key="docs_findings",
)


# The two researchers don't depend on each other, so they run concurrently.
# ParallelAgent is not an LLM either — same plain control flow as
# SequentialAgent, different semantics. Each branch MUST write its own
# output_key: shared state is the belt, and two stations writing the same slot
# is a race.
research_team = ParallelAgent(
    name="research_team",
    description="Runs the reviews and docs researchers concurrently.",
    sub_agents=[reviews_researcher, docs_researcher],
)


writer = LlmAgent(
    name="report_writer",
    model=MODEL,
    description="Writes the final report from the researchers' findings.",
    instruction="""You are Playfield's report writer. Answer the user's research
question using ONLY the findings below. You have no tools: if a fact is not in
the findings, it does not exist. Do not invent evidence.

PLAYER FINDINGS:
{reviews_findings}

DOCUMENTATION FINDINGS:
{docs_findings}

Write the report in exactly these five sections, using these headings:

## Question
Restate the question in one sentence.

## What players say
The themes players raise. Every claim ends with its review ids, e.g. (r042, r187).

## What the docs say
What the developers actually shipped or fixed. Every claim ends with its source
file and date, e.g. (g12-patch-notes.md, 2026-01-15).

## Timeline check
Compare the two: for each player complaint, was it fixed, and when? State
whether the criticism is still current or already addressed by a patch.

## Verdict
An actionable recommendation, followed by your confidence: high, medium, or low.
Base the confidence on how much evidence you actually have.

Under 400 words total.""",
    output_key="report_draft",
)


# --------------------------------------------------------------------------
# Part 4 — the quality loop: critic ⇄ reviser
# --------------------------------------------------------------------------
# The critique is DATA, not prose (§4.3): one boolean per checklist item, so a
# failure says WHICH bar wasn't met, and the reviser's exit condition is a
# boolean instead of a string match.


class Critique(BaseModel):
    """A structured verdict on one report draft."""

    every_claim_cited: bool = Field(
        description="True if every factual claim carries a review id, or a doc "
        "file name with its date. A claim with no source fails this check."
    )
    all_sections_present: bool = Field(
        description="True if all five sections are present: Question, What "
        "players say, What the docs say, Timeline check, Verdict."
    )
    timeline_check_substantive: bool = Field(
        description="True if the Timeline check actually compares complaint "
        "dates against fix dates, instead of restating the other sections."
    )
    actionable_verdict: bool = Field(
        description="True if the Verdict recommends a concrete action AND "
        "states a confidence level of high, medium, or low."
    )
    under_400_words: bool = Field(
        description="True if the whole report is under 400 words."
    )
    passed: bool = Field(
        description="True ONLY if every check above is true. If any single "
        "check is false, this must be false."
    )
    fixes: list[str] = Field(
        description="One entry per failed check, each naming the section and "
        "the concrete change needed. Empty when passed is true."
    )


critic = LlmAgent(
    name="report_critic",
    model=MODEL,
    description="Judges the report draft against Playfield's quality checklist.",
    # A judge does not chat with the defendant: no conversation history, so the
    # critic can only react to the draft itself.
    include_contents="none",
    instruction="""You are Playfield's editor. Judge the report draft below
against the quality checklist. You are strict: a draft that "reads well" but
cites nothing fails.

REPORT DRAFT:
{report_draft}

Judge each check honestly and independently. When a check fails, the fix you
list must name the section and the concrete change — "add review ids to the
two claims in What players say", not "improve citations".""",
    output_schema=Critique,
    output_key="critique",
)


reviser = LlmAgent(
    name="report_reviser",
    model=MODEL,
    description="Applies the critique to the draft, or ends the loop once approved.",
    include_contents="none",
    instruction="""You are Playfield's report reviser.

CURRENT DRAFT:
{report_draft}

CRITIQUE:
{critique}

If the critique's `passed` is true: call the exit_loop tool and output nothing
at all. The report is finished.

Otherwise: rewrite the draft so that every item in `fixes` is resolved. Keep
the five section headings, keep every citation that was already correct, and
change nothing the critique did not object to. Output ONLY the full revised
report — no preamble, no explanation of what you changed.""",
    tools=[tools.exit_loop],
    # Sends the rewrite back around the belt, to the key the critic reads.
    output_key="report_draft",
)


quality_loop = LoopAgent(
    name="quality_loop",
    description="Runs critic and reviser until the report passes or the budget runs out.",
    sub_agents=[critic, reviser],
    # The brake is exit_loop; this is the budget. A critic that is never
    # satisfied costs three rounds, not an unbounded bill.
    max_iterations=3,
)


# --------------------------------------------------------------------------
# The pipeline — extend as you go
# --------------------------------------------------------------------------

root_agent = SequentialAgent(
    name="report_pipeline",
    description="Researches a question about Playfield games and produces a structured report.",
    sub_agents=[
        research_team,
        writer,
        quality_loop,
    ],
)
