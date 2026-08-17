# Day 4 · Multi-agent systems

Last session ended with one overworked analyst producing an "okay" report. Today
you build the team that produces a *good* one: parallel researchers, a writer,
and a critic loop that measurably improves the output.

New package: `day4/playfield_report/`. Its `tools.py` is Days 1–3's finished
tools, consolidated: today you architect, you don't re-implement. Run
`adk web` from `day4/`.

**The lesson under everything today:** an agent's instruction is its *entire
job*. Small jobs → reliable agents. When one instruction juggles five jobs, the
model drops balls. Many small specialists beat one giant prompt.

---

## Part 1 · Pipelines: agents in a fixed order (09:00–10:00)

### 1.1 Run the starter pipeline

`playfield_report` already works as a two-stage pipeline. Pick it in `adk web`
and give it a real job:

> `Should Playfield feature Glacier Punk in the winter sale?`

### 1.2 Read what actually happened

This is not last session's agent with extra tools. Open **Events**:

1. `reviews_researcher` ran first: several `search_reviews` calls, then a
   bullet list of findings,
2. `report_writer` ran second: **zero tool calls**, just writing.

Two mechanics make this work (find both in `agent.py`):

- **`SequentialAgent`**: not an LLM! It's plain control flow: "run these
  sub-agents in order". No tokens, no decisions, no surprises.
- **`output_key="reviews_findings"`**: the researcher's final text is saved
  into **session state** (Day 3!) under that key, and the writer's instruction
  pulls it in with the `{reviews_findings}` placeholder.

State is the conveyor belt; agents are the stations.

### 1.3 Feel the specialization

Ask the *pipeline* something it shouldn't handle: `Hi, what can you do?`
It dutifully "researches" your greeting: a pipeline runs its stages no matter
what. **Workflow agents trade flexibility for predictability.** (The
`concierge_demo` in Part 2 shows the opposite trade.)

> **✅ Checkpoint 1:** you can point at the Events panel and narrate:
> sequential agent → researcher → state via output_key → placeholder → writer.

---

## Part 2 · Parallel research & delegation (10:10–11:00)

> **How TODOs work today:** they tell you *what* to build and *why*, not the
> code. Everything you need is in `agent.py`, `tools.py`, and Days 2–3. Design
> first, type second, and if you're stuck for more than ~10 minutes, ask us.
> That's literally why we're in the room.

### 2.1 Split the researcher (~15 min)

One researcher covers reviews only: the docs (patch notes!) never enter the
report. Build `docs_researcher`, a second specialist over the *official* docs
corpus. Before you write it, answer for yourself (the TODO in `agent.py` asks
the same questions):

- **Which tool** does a docs specialist get? Read `tools.py`, and give it
  *only* that. A specialist with every tool is not a specialist.
- **What's its quality bar?** Part 3's report will compare complaint dates
  against fix dates, so a useful docs finding looks like
  *"v1.2 fixed save corruption, 2026-01-15 (g12-patch-notes.md)"*: a fact,
  a date, a file. Write an instruction that *demands* that shape.
- **Where do its findings go?** The writer reads from state: decide the key,
  and be ready to defend why it can't be `reviews_findings`.
- **What's its scope?** The question may be pure strategy ("should we feature
  X?"): no doc answers that, and a lazily-instructed researcher will notice,
  reply "the docs don't cover this", and quit *without a single search*. Its
  job is not the question; it's the **official record of the games the
  question mentions**. Write the instruction so "not covered" is only allowed
  *after* searching.

`reviews_researcher` is your reference for the *shape*, but every line you
copy, you should be able to justify keeping or changing.

### 2.2 Run them at the same time

The two researchers don't depend on each other, so they shouldn't run in
line. ADK has a workflow agent for exactly this; you've seen it in today's
slides, and its constructor takes the same arguments you already used for
`SequentialAgent`. Build the research team, swap it into the pipeline's
`sub_agents` in place of `reviews_researcher`, and extend the writer's
instruction to use *both* findings placeholders (full template comes in
Part 3; for now just add the second one).

Refresh, re-run the Glacier Punk question, and check Events: both researchers'
calls interleave: they ran **concurrently**, each writing to its own state key.

⚠️ Parallel agents must write to **different** output_keys: shared state is
the conveyor belt, and two stations writing to the same slot is a race.

### 2.3 Side-quest: the other way to compose (AgentTool)

Workflow agents = *you* fix the control flow. The alternative: wrap an agent as
a **tool** and let a parent *model* decide when to call it. Try
`concierge_demo` in the dropdown:

- `How much is Rooftop Ramen?` → answers itself (catalog tool)
- `Do players find Kernel Panic too hard?` → delegates to the wrapped
  `review_specialist`: in Events, a whole nested agent run inside one tool call.

Rule of thumb: **fixed process → workflow agents; open-ended routing →
AgentTool.** Your report pipeline is a fixed process; that's why the main
track uses workflow agents.

> **✅ Checkpoint 2:** both researchers run in parallel into separate state
> keys, and you've seen an agent call another agent as a tool.
>
> **⭐⭐ Fast?** In `concierge_demo`, add a second specialist for docs questions
> and watch the concierge route between three options.

---

🍕 **Lunch.** After: the report grows a spine, and then an editor.

---

## Part 3 · The report, properly (11:30–12:15)

### 3.1 Give the writer a contract

Replace the writer's instruction with the full template (in
`solutions/playfield_report/agent.py` if you want to compare while typing,
but write your own wording; it's your report):

```
## Question         restate it in one sentence
## What players say  themes with review-id citations
## What the docs say  facts with file names and dates
## Timeline check    complaints vs fixes: is the criticism still current?
## Verdict           actionable recommendation + confidence (high/medium/low)
```

Under 400 words, evidence-only ("Do not invent evidence": say it explicitly;
writers are the most creative liars in any pipeline).

### 3.2 Commission reports

Run at least these two:

- `Should Playfield feature Glacier Punk in the winter sale?`
  *(the interesting one: launch was rough, but check the Timeline section
  against the 2026 hotfix arc)*
- `A studio pitched us "Chess Royale 2". What should they fix in the original first?`

Read the **Timeline check** section closely: this is the exact
reviews-vs-patch-notes comparison you did *by hand* in Day 1's exercise 7.3.
It's now a paragraph that writes itself.

> **✅ Checkpoint 3:** a five-section report with review ids, doc files, and
> dates, answering a question you'd actually take to a meeting.
>
> **⭐⭐ Fast?** Add a third parallel researcher: `catalog_researcher`
> (tools: `list_games`, `get_game_details`, output_key `catalog_findings`) that
> pulls prices and ratings context, and give the writer a "Market context" section.

---

## Part 4 · The critique loop (12:25–13:00)

### 4.1 An editor that can say "no" (~15 min)

The writer's first draft is decent. Decent isn't the bar. Design an editor
stage: a **critic** that judges the draft, a **reviser** that applies the
critique, and a **`LoopAgent`** that runs them until the critic is satisfied.
The spec is below; the *mechanics* are yours to find (the TODO in `agent.py` points at
where each answer lives):

- **The critic's checklist** (this is the acceptance contract, copy it into
  its instruction): citations on every claim · all five sections present ·
  actionable verdict with a confidence level · under 400 words. All pass →
  it replies *exactly* `REPORT APPROVED` (that's `COMPLETION_PHRASE`, an
  exact-match protocol, because "looks good I guess!" is not machine-checkable).
  Anything fails → a numbered fix list.
- **A judge shouldn't chat with the defendant.** The critic must see *only*
  the draft. Find the `LlmAgent` option that keeps the conversation out of
  its context (today's slides showed it).
- **The belt must loop back.** The reviser's rewrite has to land where the
  critic looks for the draft. One specific `output_key` makes the loop a loop;
  any other makes it a very expensive no-op.
- **Every loop needs a brake and a budget.** How does anything inside a
  `LoopAgent` say "stop"? `tools.py` has one tool you haven't used yet: read
  its docstring, then read what it *does*. And cap the iterations: a critic
  that's never satisfied plus no cap is an infinite bill. (Three is a good
  number. Be ready to say why one isn't.)

Append your loop to the pipeline's `sub_agents`.

### 4.2 Watch a report get better

Re-run the Glacier Punk question and follow Events through the loop:
draft → critique (usually catches missing citations or a mushy verdict) →
revision → `REPORT APPROVED` → exit.

**Measurably better**: don't take it on vibes. In Events, put draft v1 and the
final side by side and count: citations per section, checklist items satisfied,
words. That before/after count is your first *evaluation*, a hand-run one.

> **✅ Day-4 outcome unlocked:** a multi-agent system (parallel research,
> templated writing, self-critique) that turns a question into a defensible
> report, end to end.
>
> **⭐⭐ Fast?** Make the critic pickier (require a counter-argument in the
> Verdict). At what point does it stop converging in 3 iterations, and what
> does that teach you about acceptance criteria?

### 4.3 Type the contract (~20 min)

Look hard at your reviser. It greps the critique for a magic string. That's a
*protocol between two agents*, enforced by nothing but hope: one creative
critic ("Report approved!", "REPORT: APPROVED ✅") and the loop spends its
whole budget revising a finished report. You'd never ship two services that
talk like this. Don't let two agents.

The upgrade: make the critique **data**. `LlmAgent` takes an
`output_schema` (a Pydantic model, exactly the response schemas you wrote on
Day 1, Part 4), and then the critic *cannot* answer outside the format, and
`state["critique"]` becomes a dict instead of prose. Design the verdict model
yourself:

- one boolean per checklist item (so a failure says *which* bar wasn't met),
- an overall `passed`: describe it so it may only be true when every check is,
- a `fixes` list of strings: concrete enough that the reviser can act on each.

Then re-plumb both ends of the contract:

- **Critic:** attach the schema. Now reread its instruction: everything that
  *begs* for a format ("reply with exactly…", "a numbered list, nothing
  else") is dead weight the schema now enforces. Delete it; keep the
  judgment. (`COMPLETION_PHRASE` should end up with zero references; that's
  the point.)
- **Reviser:** its `{critique}` placeholder now renders a dict. What's the new
  exit condition? One boolean, no string matching.

Re-run Glacier Punk and open the **State** tab: `critique` is a structured
verdict you could chart, diff, or alert on. And notice what you just built:
a machine-checkable rubric scored against an agent's output. Hold that
thought until the next session.

> **✅ Checkpoint 4.3:** the loop still converges, no magic strings left in
> the file, and `state["critique"]` is a dict with per-check booleans.
>
> **⭐⭐ Fast?** Run the pipeline 3 times and tally which checklist boolean
> fails most often on draft v1. Congratulations: you're doing failure-mode
> analysis. **⭐⭐⭐** Add a `confidence: float` (0–1) per check and make the
> reviser prioritize low-confidence fixes first.

### The cliffhanger

Run the same question twice. Compare the two reports. Both good, but not the
same. Which tools ran? Same order? Same verdict?

You now own a system whose behavior you can't fully predict. On what basis
would you tell Playfield's CEO "yes, ship it"? *"I ran it twice and it looked
fine"* is not an answer. **Next session:** evaluation sets, tracing, and the
discipline of trusting an agent, including knowing when NOT to add one more.

---

## Part 5 · The Playfield Pulitzer (optional finale)

You can't predict your system. So let's stress it in public. Every pipeline
in the room files a report on the **same** CEO question, live in the course
Discord's `#playfield-boardroom`. Then the knives come out: your *critic*
reviews someone else's report. Two prizes at the end: 🏆 the **Pulitzer** for
the best-cited correct report, and 🔪 **most brutal fair critic** for the fix
list that was harsh *and* entirely right.

New package: `day4/boardroom/`, your envoy to the channel. Same server-side
two-tool boundary as the Day-3 support desk (read one channel, post signed),
plus one upgrade: posts longer than one Discord message are auto-split into a
chunk chain.

### 5.1 Brief your envoy (~8 min)

Set two lines in the repo `.env`: `DISCORD_MCP_URL=http://<ip>:8765/mcp` (we
dictate the ip) and `PULITZER_HANDLE=<your name in the boardroom>`; reviewers
will hunt your report by that byline.

Then open `boardroom/agent.py` and work the two TODOs. The design questions
are in the file; the short version:

- The pipeline itself can't post: a `SequentialAgent` runs its stages and
  takes no orders. You know the Part-2 mechanism that fixes that.
- The finished report never comes back as the tool's return value (the loop
  ends on `exit_loop`, so no text). It arrives via **session state**, which
  crosses the AgentTool boundary, and the instruction's
  `{report_draft?}` placeholder (the `?` = optional, empty before the first
  run) is re-read from state before every model call. State is still the
  conveyor belt, even here.
- The checklist your envoy enforces in reviews is **your** critic's checklist.
  Copy your own wording in. Whose acceptance criteria are right is about to
  become a public question.
- Day-3 rule, sharpened: everything in that channel is written by rivals:
  data to judge, never instructions to follow. If a report sweet-talks its
  reviewer into an APPROVED, that's a failed review *and* a lesson.

### 5.2 File your report (~12 min)

The CEO's question drops in the channel. Tell your envoy to file a report.
Watch Events: read the channel → your whole pipeline runs *inside one tool
call* → the report posts, signed and threaded under the question. Then watch
the channel fill with everyone else's. They all look plausible, don't they?

### 5.3 The critic swap (~10 min)

You get assigned a rival byline (yours + 1 on the roster, wrapping around).
Tell your envoy: `review <their handle>'s report`. It reassembles their chunk
chain, judges it against YOUR checklist, and posts the verdict under their
report. Do not soften it. Fair and ruthless.

### 5.4 The reveal

Watch the channel. Somewhere in there, one report got `APPROVED` by one critic
and a five-point demolition from another, for the *same text*. Both critics
ran honestly. So which one is right?

Sit with how unanswerable that is without an agreed rubric and agreed ground
truth. Then vote the Pulitzer.

> **✅ Finale unlocked:** your report is in the boardroom with your name on
> it, your critique is under someone else's, and you've watched two honest
> critics disagree about the same report. Next session opens exactly there.
