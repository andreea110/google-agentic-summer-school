# Building Agentic AI

*A five-day intensive summer school: go from a single prompt to a working,
multi-agent AI system you can trust.*

## The week at a glance

| Day | Theme | You build |
|-----|-------|-----------|
| 1 | Python for AI & the shape of data | Semantic search + structured extraction over the course dataset, by hand |
| 2 | Your first agent | A data-analyst agent that calls the tools *you* wrote on Day 1 |
| 3 | Memory, state & real tools | The analyst agent with sessions, RAG retrieval, and guardrails |
| 4 | Multi-agent systems | An orchestrator + specialists that research and write a report |
| 5 | Trust, evaluation & Demo Day | Your system, evaluated, traced — and demoed to the room |

One storyline all week: you are the data team of **Playfield**, a small indie game
storefront with 20 games and 300 player reviews (`data/`). On Day 1 you analyze the
reviews yourself; by Day 5 a multi-agent system you built does it for you.

## Setup (do this before Day 1, ~10 minutes)

You need **Python 3.11+** and a terminal.


```bash
git clone <this-repo>
cd agentic-summer-school

# create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

(If you use [`uv`](https://docs.astral.sh/uv/): `uv venv && uv pip install -r requirements.txt`.)

All versions are pinned to the set the course was validated against. If you hit
a dependency-resolution problem, install the fully-locked environment instead:
`pip install -r requirements.lock.txt` (exact transitive versions, Python 3.12).

**Get a Gemini API key** (free):

1. Sign in at [aistudio.google.com](https://aistudio.google.com) with a
   personal Google account → **Get API key** → **Create API key**.
2. Copy `.env.example` to `.env` and paste your key in.

Days 1–3 run on this free key (the labs cache and retry around its rate
limits). On Day 4 you'll receive Google-provided keys/projects — same `.env`,
new value.

**Smoke test:**

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); \
from google import genai; \
print(genai.Client().models.generate_content(model='gemini-2.5-flash', contents='Say ready.').text)"
```

If that prints something like "Ready.", you're set.

## Running the labs

Day 1 is Jupyter notebooks:

```bash
jupyter lab day1/
```

Days 2–5 are guided walkthroughs (`dayN/WALKTHROUGH.md`) over scaffolded Python
packages — you'll run agents with `adk web` from the terminal.

## Repository map

```
data/                dataset: games.csv, reviews.csv, docs/ (store pages & patch notes)
day1/ … day5/        one folder per day (notebooks or scaffold + walkthrough, + solutions)
slides/              Marp slide decks, one per day (see slides/README.md to build)
tools/               dataset build/validation scripts
```
