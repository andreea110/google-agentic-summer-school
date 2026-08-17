# Day 1 · Python for AI & the shape of data

Welcome to Playfield. 🎮 You're the new data person at a small indie game
storefront: 20 games, 300 player reviews, and studios that keep asking
*"what are players actually saying?"* This week you'll build an AI system that
answers them. Today, you learn to do its job by hand.

**Outcome:** a working semantic-search and structured-extraction pipeline over the
review corpus — you, doing manually what your agent will do by Day 5.

## Before you start

Complete the [setup in the root README](../README.md): venv and
`pip install -r requirements.txt`. Then get your **free Gemini API key**:

1. Sign in at [aistudio.google.com](https://aistudio.google.com) with a
   **personal Google account**.
2. Click **Get API key** → **Create API key** (creating a new project is fine).
3. In the repo root: `cp .env.example .env` and paste the key in
   (`GOOGLE_API_KEY=AIza…`).
4. Run the smoke test from the root README — it should print "Ready.".

The free tier is all Days 1–3 need. On Day 4 you'll receive Google-provided
keys for Days 4–5 and simply replace the value in `.env`. Then:

```bash
jupyter lab day1/
```

## Schedule

| Time | Notebook | What you'll learn |
|--------------|----------|-------------------|
| 1 hour | `part1_llms.ipynb` | LLMs are token generators: first API calls, temperature, statelessness, hallucination |
| ☕ 10 min | | |
| 50 min | `part2_vectors.ipynb` | numpy, cosine similarity from scratch, Gemini embeddings, meaning as geometry |
| 🍕 30 min | | |
| 45 min | `part3_search.ipynb` | pandas + the corpus, why keyword search fails, semantic search in ~15 lines |
| ☕ 10 min | | |
| 35 min | `part4_extract.ipynb` | structured output with `response_schema`, messy reviews → clean DataFrame → the chart |

## How to work

- Run every cell yourself; don't just read. The notebooks are written to be
  self-explanatory, so if you fall behind you can always catch up.
- Exercises are star-rated: ⭐ everyone · ⭐⭐ if you're cruising · ⭐⭐⭐ show-off
  territory. Solutions are in [`solutions/`](solutions/) — try first, peek second.
- Each notebook ends with a **✅ checkpoint**. If you can't tick it, flag a mentor
  at the break — Day 2 builds directly on today's code.
- Rate-limit errors (`429`) are normal on free keys: the notebooks retry
  automatically, and everything expensive is cached in `day1/cache/`.

## Keep your work

Next session your `search()` and `analyze()` functions become **agent tools** —
the model will call them on its own. Don't delete anything.
