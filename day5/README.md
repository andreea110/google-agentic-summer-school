# Day 5 · Trust, evaluation & the tournament

Nondeterminism, evaluation sets, tracing — the difference between *"it worked
when I tried it"* and *"here's the evidence."* Then: **Agentic Mafia** — the
classic social-deduction game (Romanian schoolyards know it as «Killer,
preda-te!»), played live by every student's agent.

**Outcome:** an evaluated, traceable agent that survives (or wins) a live
social-deduction tournament against the whole room.

| Time | Part | Focus |
|------|------|-------|
| 09:00–10:00 | 1 · Evaluation | nondeterminism, eval sets, `adk eval`, reading failures |
| 10:10–11:00 | 2 · Tracing | trace-driven debugging, extending the eval suite |
| 11:30–12:15 | 3 · The discipline + your player | trust checklist, when NOT to add an agent, build your player |
| 12:25–13:00 | 4 · The tournament 🔪 | Agentic Mafia on the projector |

Start here → [`WALKTHROUGH.md`](WALKTHROUGH.md)

Contents: `playfield_agent/` (the analyst, frozen at Day-3 final state — the
eval target), `evals/` (smoke eval set + metric config; regenerate with
`python tools/make_evalset.py` from the repo root), `mafia_server/` (the MCP
game server + dashboard + scripted bots; instructor runs it), `mafia_agent/`
(the starter player you extend), `solutions/` (a reference player — the
tournament outranks it).
