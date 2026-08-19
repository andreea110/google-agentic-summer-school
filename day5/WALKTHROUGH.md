# Day 5 · Trust, evaluation & the tournament

Last session ended with a question: on what basis would you tell Playfield's CEO
*"yes, ship it"*? This morning you earn that answer. This afternoon, your agent
plays **Agentic Mafia** against everyone else's — live, on the projector.

`day5/playfield_agent/` is the analyst in its final form (frozen Day-3 state):
a stable target to evaluate. The afternoon's player agent lives in
`day5/mafia_agent/`.

---

## Part 1 · "It works" is a claim, not a fact (09:00–10:00)

### 1.1 Meet nondeterminism, again

Run this question **three times in three fresh sessions** against
`playfield_agent` (from `day5/`, `adk web`):

> `What do players think about the difficulty of Kernel Panic?`

Compare: same tools? same order? same wording? same *conclusion*? Usually the
conclusions agree while everything else varies. So what exactly are you testing
when you test an agent? Not strings, but **behavior**: did it use the right
sources, and did it land on a correct, grounded answer?

### 1.2 An eval set is that question, written down

Open [`evals/analyst_smoke.evalset.json`](evals/). Four cases, each with:

- `user_content`: the question we ask,
- `tool_uses`: the tool trajectory we *expect* (names + args),
- `final_response`: a *reference* answer (from
  `instructor/dataset-ground-truth.md`; the dataset was designed with answer
  keys; today they surface).

And [`evals/test_config.json`](evals/test_config.json) holds the metrics:

| Metric | Measures | How |
|---|---|---|
| `tool_trajectory_avg_score` | did it call the expected tools with expected args | exact match, no LLM |
| `response_match_score` | how close is the wording to the reference | ROUGE overlap, no LLM |

### 1.3 Run it

```bash
cd day5
adk eval playfield_agent evals/analyst_smoke.evalset.json \
    --config_file_path evals/test_config.json \
    --print_detailed_results
```

*(~2-3 minutes: it's actually running your agent four times.)*

### 1.4 Read the failures. They're the curriculum

Expect a **mixed** scorecard, on purpose:

- `price_and_developer` likely passes: deterministic question, deterministic
  trajectory.
- `worst_netcode` / `save_bug_fixed`: trajectory may *fail* even when the
  answer is right: the agent phrased its search query differently than our
  expectation, and exact-match scoring is merciless about it.
- `refund_guardrail` passes with **zero tools**: the callback answered before
  the model ran. Guardrails are testable too.

**🔍 The lesson:** a failing eval means one of *three* things: the agent is
wrong, the *expectation* is wrong, or the *metric* is too strict. Exact-match
trajectories suit deterministic lookups; fuzzy behavior needs fuzzier judges
(ADK also ships LLM-judged metrics like `final_response_match_v2` and
rubric-based scoring: same eval sets, smarter graders, extra cost).

> **✅ Checkpoint 1:** you ran an eval suite, and for each failing case you can
> say *which* of the three things was wrong.

---

## Part 2 · Tracing: what did it actually do? (10:10–11:00)

### 2.1 One question, under the microscope

Ask the analyst the save-bug question, then open **Events** and click through
to the **Trace** view. For each step you can see the exact model request
(instruction + history + tool declarations), the tokens, the latency, the tool
calls with args and responses. This is the difference between *"it seems
confused"* and *"the second search returned the wrong game's patch notes, and
it never searched again."*

### 2.2 Debug a real miss

Take a failure from Part 1 (or induce one: ask something ambiguous like
`Is the chess game any good?`). In the trace, find the **first wrong step**:
bad routing (instruction problem)? bad query (tool-description problem)? bad
synthesis (evidence was there, conclusion wasn't)? Fix the actual layer, not
the symptom, re-run the eval, watch the score move. That loop, eval → trace →
fix → eval, is agent engineering in one sentence.

### 2.3 Extend the suite

Add a fifth case for the fix you just made (or any behavior you care about):
easiest path: ask the question in `adk web`, verify the run, and use the
**Eval** tab to save that session as an eval case; or extend
`tools/make_evalset.py` (the ground-truth file has more seed questions) and
regenerate. Re-run. **Every behavior you rely on deserves a case that will
scream when it breaks.**

> **✅ Checkpoint 2:** you traced a failure to its first wrong step, fixed that
> layer, and pinned the behavior with a new eval case.

---

🍕 **Lunch.** After: the recap that makes it a discipline — then you build a
player and send it into the arena.

---

## Part 3 · The discipline, then your player (11:30–12:15)

### 3.1 The trust checklist (15 min, with slides)

Everything this week, as the checklist you take home:

1. **Grounding**: facts come from tools/retrieval, never model memory (D1, D3)
2. **Structure**: schemas at every model boundary (D1, D4)
3. **Honest failure**: tools return errors; agents admit "not found" (D2, D3)
4. **Memory by design**: state is explicit, prefixed, inspectable (D3)
5. **Guardrails in layers**: callbacks, tool checks, instructions (D3)
6. **Small jobs**: one agent, one instruction, one competence (D4)
7. **Bounded loops**: every cycle has an exit and a cap (D4)
8. **Evals + traces**, or you're shipping vibes (D5)

And the ninth: **know when NOT to add an agent.** An agent earns its place only
when a *decision* must be made in language. A fixed transformation is a
function; a fixed order is a pipeline; a schema fills a slot. The best systems
you built this week are mostly *not* agents; they're good engineering with a
few small agents where judgment lives.

### 3.2 The game: Agentic Mafia

The classic social-deduction game — Romanian schoolyards know it as «Killer,
preda-te!» — a killer hides among the townsfolk, eliminates them one by one,
and the town's only weapon is talking it out. Except here every player is an
**agent you students wrote**. The game server is an
MCP server (Day 3's third kind of tool): it enforces every rule, so nobody
plays outside the engine. The only variable is how well your agent thinks.

**Roles** (secretly assigned when the instructor starts the table):

| Role | Team | Special power |
|------|------|---------------|
| 🔪 **Killer** (server-configured count) | killers — they know each other | picks a victim each round (team plurality; tie → random among tied) |
| 💉 **Healer** | town | protects one player per round (self allowed); a heal blocks the *kill*, never the vote |
| 🧑‍🌾 **Civilian** | town | none — words and votes only |

**Each round:**

1. **TALK** — every living player submits exactly **one** public message
   (≤300 chars). Messages are revealed *simultaneously* when everyone has
   spoken — no reading before you commit.
2. **ACT** — everyone secretly **votes to lynch** (plurality; any tie →
   nobody dies; `""` abstains). Killers also pick a victim; healers also
   pick a protectee. **Exception: no lynch in round 1** — the town has
   nothing to go on yet, so the first night is kill + heal only.
3. **DAWN** — deaths are announced *with causes* ("lynched" / "killed");
   a blocked kill is announced without naming who was saved. Dead players'
   roles stay **unknown** unless the instructor runs the server with
   `--reveal-dead-roles` (the classic-Mafia "flip") — so only trust role
   claims your agent can actually derive.

**Winning:** the town wins when every killer is dead; the killers win when
they equal or outnumber everyone else. Stall past the round cap and *nobody*
wins.

**Four server rules that shape your design:**

- `join_game` returns a **secret token**; every other tool needs it. Anyone
  who learns it can play your turns — never put it in a chat message.
- `next` is a **long-poll**: it holds your request until the game moves, so
  your agent never wastes an LLM turn asking "anything yet?". The loop is
  simply: `next` → do what its `to_do` says → `next` → …
- The server only ever shows the **current round's chat**. Round 3's agent
  has no server-provided memory of round 1 — carrying (and *distilling*)
  history is your agent's job.
- An agent that neither talks nor acts for two consecutive rounds
  **vanishes** — a crashed player can't hold the town hostage.

**The four tools** (this is the entire API — everything else is strategy):

| Tool | Args | Does |
|------|------|------|
| `join_game` | `player_name` — your unique name | Call **once, first**. Returns your secret `token` (every other tool needs it) and your `table` number. |
| `next` | `token` | The heartbeat. Returns the current game state, **long-polling** up to ~20 s until something new happens — call it in a loop, forever. |
| `send_message` | `token` · `message` (≤300 chars, longer is truncated) | Your one public statement. TALK phase only, once per round; revealed simultaneously with everyone else's. |
| `submit_action` | `token` · `vote` · `kill_target` (killers only) · `heal_target` (healers only) · `reasoning` (optional) | Your secret move. ACT phase only, once per round. `""` = abstain; targets must be living players; **no vote in round 1**. `reasoning` is one private sentence on *why* — only the instructor's dashboard ever sees it, no player does, and it changes nothing in the game. (Bonus: agents forced to articulate a why often *choose* better.) |

What `next` returns — the fields your agent should actually read:

- **`to_do`** — plain-language orders for right now. An agent that does
  nothing but obey this field plays a legal game.
- `status` / `phase` / `round` — `waiting` means nothing new yet: call
  `next` again.
- `you` — your name, whether you're alive, your `role`, and (killers only)
  `your_fellow_killers`.
- `rules` — table size and the killer/healer counts. Deduction fuel.
- `players_alive` — the only valid targets.
- `news` — the dawn announcements (deaths + causes, saves).
- `chat` — this round's messages, present once everyone has spoken.
- `winner` + `roles_revealed` — once the game ends.

Every tool returns `{"error": "..."}` instead of raising (Day 3's lesson,
enforced): the message tells your agent exactly what it got wrong — wrong
phase, invalid target, double submit — so read it, fix the call, continue.

### 3.3 Build your player

The starter is `mafia_agent/` — it already knows the rules and plays
legally (and terribly). Get it moving first, then make it dangerous.

**Step 3.3 — the token callback.** The token currently survives only in the
model's chat history — one long game away from being garbled. Day 3's
answer: explicit state. Open `mafia_agent/callbacks.py`, implement
`save_token` (an `after_tool_callback` that catches `join_game`'s result
and stores the token under `game:token`), wire it up in `agent.py`, and add
`Your saved token (if any): {game:token?}` to the instruction so the model
always sees it. Print `tool_response` once to discover its shape — same
move as Day 2's Events tab, one layer down.

**Test loop** (no instructor needed — run your own war room):

```bash
cd day5
python -m mafia_server --tables 1 --table-size 5 --killers 1 --healers 1 &
python -m mafia_server.simulate --players 4        # scripted sparring bots
python -m mafia_agent.play --name yourname          # your agent, autonomous
# then open http://localhost:8000/dashboard?key=…  (key printed at startup)
# and press ▶ start
```

By default the game is **host-paced**: each chat reveal and each dawn waits
for the ⏭ button on the dashboard, so *you* control the tempo while you read
what your agent said. Flip a table to ⏩ auto (or start the server with
`--pace auto`) to let a game run out unattended.

`adk web` also works for poking at your player by hand ("join as X and
play") — but read `mafia_agent/play.py`: the whole difference between a
chatbot and an autonomous agent is that outer while-loop.

**Step 3.4 — strategy.** Rewrite `STRATEGY` in `agent.py`. This is the
assignment; the beatable bots are the floor. Ideas, ⭐-rated:

| Upgrade | ⭐ | The idea |
|---------|---|----------|
| Role-split strategy | ⭐ | different instructions for killer / healer / civilian — one paragraph each beats one vague blob |
| The notes ledger | ⭐⭐ | every round, rebuild a compact `NOTES` block (alive, dead+causes, suspicion table, what you've claimed publicly). Votes come from the ledger, not from vibes — this is context engineering, the skill the whole week has been sharpening |
| The red-team critic | ⭐⭐ | a Day-4 `AgentTool` sub-agent that attacks your *draft* message ("what could a paranoid reader infer?") before you send it. Self-critique loops are the most transferable pattern in this course |
| Opponent models | ⭐⭐⭐ | per-player dossiers: what did each player claim, whom did they push, who benefited from each death? Killers are inconsistencies wearing a name |

Fill seats with `simulate.py` bots and play full games. Iterate. The eval
lesson from this morning applies verbatim: *"it played well once"* is a
claim, not a fact.

> **✅ Checkpoint 3:** your agent finishes a full local game against 4 bots
> without errors, with the token callback wired, and its messages sound like
> a player — not like an AI reading rules aloud.

---

## Part 4 · The tournament 🔪 (12:25–13:00)

The instructor's server goes up on the LAN; the dashboard goes on the
projector.

1. **Connect**: `export MAFIA_SERVER_URL="http://<instructor-ip>:8000/mcp"`,
   then `python -m mafia_agent.play --name <your-name>` (unique name — the
   server rejects duplicates).
2. **Tables fill**, the instructor presses ▶, and roles land in secret.
3. **Watch the projector**: the town chat scrolls live, deaths are announced
   at dawn, and the instructor can hover any player to see their words —
   and, with the reveal toggle, their secret moves. Nobody else knows who
   the killers are until the dashboard says so. Cheer accordingly.
4. Between games the instructor reshuffles tables. Killers win a game?
   Civilians talk it over — that's the point of the whole genre.

While watching: note **one message that fooled you** and one that gave its
author away. Say them out loud at the end — that's the day's real debrief:
deception and detection are *prompt engineering, scored live*.

> **✅ Course outcome unlocked:** an autonomous multi-agent system — built,
> evaluated, and battle-tested against the whole room. On Day 1 you asked a
> model questions. Today your agent lied to twenty other agents and (maybe)
> got away with it.

### Where to go next

- **ADK docs**: deployment (`adk deploy`), streaming, MCP tools, more metrics
- Rebuild this week's system over **your own data**; the pipeline is the same
  15 lines all the way down
- Your player is a portfolio piece: clean it, README it, ship it to GitHub —
  and the game server is open in `mafia_server/` if your friends want a
  tournament of their own
