# Day 3 · Memory, state & real tools

Last session's agent forgot everything between sessions and couldn't see the docs.
Today: **session state** (a real watchlist that survives), **tool-failure
design**, the full **tool taxonomy** (custom, built-in `google_search`, and an
**MCP** server demo), a **RAG tool** over the patch-notes corpus, and
**callbacks** for logging + a refund guardrail.

**Outcome:** the analyst agent, now with memory and retrieval over a document
set — plus its first observability and safety layers.

| Time | Part | Focus |
|------|------|-------|
| 50m | 1 · Sessions & state | state dict, `user:` prefix, watchlist tools |
| 65m | 2 · The tool ecosystem | structured errors vs raises, built-in `google_search`, MCP tools |
| 40m | 3 · A real RAG tool | index `data/docs/`, `search_docs`, the "did they fix it?" payoff |
| 35m | 4 · Callbacks | tool-call logging, refund guardrail, defense in depth |
| 🏆 | 5 · Field day: the support desk | your agent answers live `#playfield-support` questions via a remote MCP server — and takes no bait |

## One-time setup: Node.js (for the MCP demo)

Part 2's `mcp_demo` launches an MCP server with `npx`, which ships with
Node.js. Check first — any LTS version (≥ 18) is fine:

```bash
node --version && npx --version
```

If missing:

- **Linux** — use your distro's package manager:
  `sudo apt install nodejs npm` (Debian/Ubuntu) ·
  `sudo dnf install nodejs npm` (Fedora) ·
  `sudo pacman -S nodejs npm` (Arch)
- **macOS** — `brew install node`, or the installer from
  [nodejs.org](https://nodejs.org)
- **Windows** — `winget install OpenJS.NodeJS.LTS` in a terminal, or the
  installer from [nodejs.org](https://nodejs.org) — then open a **new**
  terminal so `npx` is on PATH

No Node? No drama — `mcp_demo` is a side-quest; everything else today runs
without it. *(Your first `mcp_demo` question downloads the server package via
`npx`, so it takes a few extra seconds.)*

Start here → [`WALKTHROUGH.md`](WALKTHROUGH.md) · End-of-day state → [`solutions/`](solutions/)

The scaffold already contains Day 2's finished agent — if your Day 2 didn't get
finished, today still works.
