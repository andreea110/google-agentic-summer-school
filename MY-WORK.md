# What I wrote in this fork

This is a fork of the Building Agentic AI summer school (Google Romania,
August 2026). The labs, the agent skeletons and the `TODO(you)` prompts belong
to the course and were written by Alex Gherghina. This file points at the parts
I filled in, since they are spread across three commits in a history that is
mostly his.

## Days 1–3 — tools, retrieval, callbacks

[`day1/`](day1) — embeddings and semantic search over the Playfield corpus, and
structured extraction with a response schema.

[`day2/playfield_agent/`](day2/playfield_agent) and
[`day3/playfield_agent/`](day3/playfield_agent) — an ADK `LlmAgent` with custom
tools and session state, a retrieval-augmented `search_docs` tool, callbacks for
tool logging, a refund guardrail and citation recording, a remote MCP toolset,
and hardening against prompt injection.

## Day 4 — the report pipeline

[`day4/playfield_report/agent.py`](day4/playfield_report/agent.py)

The starting pipeline had one researcher reading player reviews, so the official
record — patch notes, store pages — never reached the report. I added a second
researcher over the docs corpus, and put the two behind a `ParallelAgent`: they
do not depend on each other, so there is no reason for one to wait. Each writes
its own state key, because two branches sharing a slot is a race.

Then the editing loop. The obvious version has the critic answer in prose and
the reviser match on a phrase like `REPORT APPROVED` — which breaks the moment
the critic writes "Report approved!" instead. So the critique is data: a
Pydantic model with one boolean per checklist item, an overall `passed`, and a
list of fixes. The reviser exits on a boolean, and the critic runs with
`include_contents="none"` so it judges the draft rather than the conversation.

## Day 5 — playing Mafia, and checking the analyst

[`day5/mafia_agent/`](day5/mafia_agent)

The server only shows the current round's chat, so the agent has no history to
re-read. Its memory has to be rebuilt every round, which is what the strategy
does: a ledger of who is alive, who died and how, who claimed what, who pushed a
vote at whom, and a suspicion score per player with a reason attached. Votes are
secret, so the public message is the only lever the game gives you, and it is
written to carry a name and a verifiable reason rather than a question.

[`day5/evals/`](day5/evals) — `analyst_deterministic.evalset.json` for questions
with one right answer, `analyst_fuzzy.evalset.json` for the open ones, and a
judge configuration whose rubric requires every factual claim to come from a
tool result rather than from the model's own memory. The smoke set and the base
test config in that directory are the course's.
