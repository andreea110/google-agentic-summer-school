# Day 4 · Multi-agent systems

Why many small, specialized agents beat one giant prompt — and how to compose
them: `SequentialAgent`, `ParallelAgent`, `LoopAgent`, and `AgentTool`.

**Outcome:** a multi-agent system that researches a question over both corpora
and produces a structured, self-critiqued report, end to end.

| Time | Part | Focus |
|------|------|-------|
| 09:00–10:00 | 1 · Pipelines | SequentialAgent, output_key state hand-off |
| 10:10–11:00 | 2 · Parallel & delegation | ParallelAgent researchers, AgentTool demo |
| 11:30–12:15 | 3 · The report | writer template: players + docs + timeline + verdict |
| 12:25–13:00 | 4 · Critique loop | LoopAgent critic/reviser, exit_loop, typed verdict via output_schema |
| encore | 5 · The Playfield Pulitzer *(optional)* | every pipeline files a report to Discord; critics peer-review each other |

Start here → [`WALKTHROUGH.md`](WALKTHROUGH.md) · End-of-day state → [`solutions/`](solutions/)

Packages: `playfield_report/` (main track, staged scaffold — Part 1 works out
of the box), `concierge_demo/` (AgentTool side-quest), and `boardroom/`
(Part-5 finale — your envoy to `#playfield-boardroom`).
