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

from . import tools

load_dotenv(tools.repo_root() / ".env", override=True)

MODEL = "gemini-3.5-flash-lite"

COMPLETION_PHRASE = "REPORT APPROVED"


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

# TODO(you) — Part 2 (§2.1–2.2). Right now the OFFICIAL docs — patch notes,
# store pages — never reach the report. Fix that:
#
#   1. Build a second researcher that covers the docs corpus. Before you type:
#      which tool does it need (read tools.py)? What does a *citable* docs
#      finding look like, given that the report's Timeline section will compare
#      complaint dates against fix dates? Where must its findings land so the
#      writer can read them — and why can't it share the reviews researcher's
#      slot on the belt?
#   2. The two researchers don't depend on each other, so they shouldn't wait
#      in line. There's a workflow agent for exactly this — you already have a
#      SequentialAgent below as a construction example.
#
# Done when: Events shows both researchers' tool calls interleaving, and each
# writes its own state key. Stuck > 10 min? That's what we're here for — ask.


writer = LlmAgent(
    name="report_writer",
    model=MODEL,
    description="Writes the final report from the researchers' findings.",
    # Part 3, step 3.1: replace this instruction with the full REPORT template
    # (see WALKTHROUGH — the {reviews_findings} / {docs_findings} placeholders
    # are filled from session state automatically).
    instruction="""Answer the user's research question using ONLY these findings:

{reviews_findings}

Write 2-3 paragraphs. Keep the review ids as citations.""",
    output_key="report_draft",
)


# --------------------------------------------------------------------------
# Part 4 — the quality loop (you design it; requirements in WALKTHROUGH §4.1)
# --------------------------------------------------------------------------
# TODO(you) — an editor stage: a critic that judges the draft against the
# quality checklist, and a reviser that applies the critique — looping until
# the critic is satisfied. Questions your design must answer (the answers are
# in this file, in tools.py, and in Day 3's state lesson — not in a comment):
#
#   - The critic must judge ONLY the draft, not the chat history. Which
#     LlmAgent option removes the conversation from an agent's context?
#   - How does the critic signal "done" so the reviser can tell approval apart
#     from a fix list? (COMPLETION_PHRASE is defined above for a reason.)
#   - The reviser's rewrite must go back around the belt. Which output_key
#     forces that?
#   - How does anything inside a LoopAgent actually STOP the loop? (Read the
#     docstring of the one tool in tools.py you haven't used yet.)
#   - What happens if the critic is never satisfied — and which LoopAgent
#     argument makes that a bounded cost instead of an infinite bill?
#
# TODO(you) — Part 4, §4.3: once the loop works, look hard at the reviser.
# It branches on a MAGIC STRING — one creative critic ("Report approved!")
# and the loop burns its whole budget revising a finished report. Upgrade the
# contract: give the critic an `output_schema` (a Pydantic model — you wrote
# response schemas on Day 1, Part 4) so the critique lands in state as DATA:
# one boolean per checklist item, an overall `passed`, and a `fixes` list.
#   - What can you DELETE from the critic's instruction once the schema
#     enforces the format instead of the prose begging for it?
#   - What does the reviser's exit condition become?
#   - Why does COMPLETION_PHRASE disappear from this file entirely?


# --------------------------------------------------------------------------
# The pipeline — extend as you go
# --------------------------------------------------------------------------

root_agent = SequentialAgent(
    name="report_pipeline",
    description="Researches a question about Playfield games and produces a structured report.",
    sub_agents=[
        reviews_researcher,   # Part 2: this slot becomes your parallel research team
        writer,
        # Part 4: your quality loop joins the line here
    ],
)
