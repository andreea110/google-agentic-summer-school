"""Day 4 — the finished Playfield tools, consolidated.

These are Days 1-3's tools in their final form (in a real project this would be
a shared library, not a copy). Today is about ARCHITECTURE — you won't edit
this file except to read it.

One newcomer at the bottom: `exit_loop`, the tool that lets an agent inside a
LoopAgent say "we're done here" (Part 4).
"""

import functools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from google import genai
from google.genai import types
from google.adk.tools import ToolContext

GEN_MODEL = "gemini-3.5-flash-lite"
EMBED_MODEL = "gemini-embedding-001"

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------

def repo_root() -> Path:
    p = Path(__file__).resolve().parent
    while not (p / "data" / "games.csv").exists():
        if p == p.parent:
            raise RuntimeError("Could not locate the repo root (data/games.csv).")
        p = p.parent
    return p


@functools.lru_cache(maxsize=1)
def _client() -> genai.Client:
    return genai.Client()


@functools.lru_cache(maxsize=1)
def _games() -> pd.DataFrame:
    return pd.read_csv(repo_root() / "data" / "games.csv")


@functools.lru_cache(maxsize=1)
def _reviews() -> pd.DataFrame:
    return pd.read_csv(repo_root() / "data" / "reviews.csv").merge(_games(), on="game_id")


def _embed(texts: list[str] | str, task_type: str) -> np.ndarray:
    if isinstance(texts, str):
        texts = [texts]
    for attempt in range(7):
        try:
            result = _client().models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=768),
            )
            vectors = np.array([e.values for e in result.embeddings])
            return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        except genai.errors.APIError:
            time.sleep(2**attempt)
    raise RuntimeError("embedding failed after 7 attempts")


@functools.lru_cache(maxsize=1)
def _review_vectors() -> np.ndarray:
    cache_file = repo_root() / "day1" / "cache" / "review_embeddings.npy"
    if cache_file.exists():
        return np.load(cache_file)
    print("Day-1 cache not found — embedding 300 reviews (one-time, ~1 min)…")
    vectors = _embed(_reviews()["review_text"].tolist(), task_type="RETRIEVAL_DOCUMENT")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_file, vectors)
    return vectors


@functools.lru_cache(maxsize=1)
def _doc_index() -> tuple[np.ndarray, list[dict]]:
    vectors_file = CACHE_DIR / "doc_vectors.npy"
    meta_file = CACHE_DIR / "doc_meta.json"
    if not vectors_file.exists():
        docs_dir = repo_root() / "data" / "docs"
        paths = sorted(docs_dir.glob("*.md"))
        texts = [p.read_text(encoding="utf-8") for p in paths]
        print(f"Embedding {len(paths)} docs (one-time)…")
        vectors = _embed(texts, task_type="RETRIEVAL_DOCUMENT")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(vectors_file, vectors)
        meta_file.write_text(
            json.dumps([{"file": p.name, "text": t} for p, t in zip(paths, texts)]),
            encoding="utf-8",
        )
    return np.load(vectors_file), json.loads(meta_file.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Research tools
# --------------------------------------------------------------------------

def list_games() -> dict:
    """Lists every game in the Playfield catalog with its overall review rating.

    Use this to find a game's id from its title, or to survey the catalog.

    Returns:
        dict: status, and a list of games with game_id, title, genre,
        price_eur, release_year, developer, and pct_recommended (0-100).
    """
    stats = _reviews().groupby("game_id")["recommended"].mean().round(2) * 100
    games = _games().copy()
    games["pct_recommended"] = games["game_id"].map(stats)
    return {"status": "success", "games": games.to_dict(orient="records")}


def get_game_details(game_id: str) -> dict:
    """Gets full catalog details and review statistics for one game.

    Args:
        game_id: The game's id, e.g. 'g01'.

    Returns:
        dict: status, catalog fields and review stats (n_reviews,
        pct_recommended, median_hours_played).
    """
    rows = _games()[_games()["game_id"] == game_id]
    if rows.empty:
        return {
            "status": "error",
            "message": f"Unknown game_id {game_id!r}. Call list_games to see valid ids.",
        }
    game = rows.iloc[0].to_dict()
    reviews = _reviews()[_reviews()["game_id"] == game_id]
    game.update(
        n_reviews=int(len(reviews)),
        pct_recommended=round(float(reviews["recommended"].mean()) * 100, 1),
        median_hours_played=float(reviews["hours_played"].median()),
    )
    return {"status": "success", **game}


def search_reviews(query: str, top_k: int = 5) -> dict:
    """Searches all 300 player reviews by MEANING, not keywords.

    Use for anything players say, feel, or complain about. Prefer specific
    queries ("crashes after updates") over vague ones ("problems").

    Args:
        query: What to look for, phrased naturally.
        top_k: How many reviews to return (default 5).

    Returns:
        dict: status, and hits with review_id, title, recommended,
        score (0-1), and review_text.
    """
    q = _embed(query, task_type="RETRIEVAL_QUERY")[0]
    scores = _review_vectors() @ q
    top = np.argsort(scores)[::-1][:top_k]

    df = _reviews()
    hits = []
    for i in top:
        row = df.iloc[int(i)]
        hits.append(
            {
                "review_id": row["review_id"],
                "title": row["title"],
                "recommended": bool(row["recommended"]),
                "score": round(float(scores[int(i)]), 3),
                "review_text": row["review_text"],
            }
        )
    return {"status": "success", "hits": hits}


def search_docs(query: str, top_k: int = 3) -> dict:
    """Searches Playfield's official docs: store pages and dated patch notes.

    The source of truth for FACTS: features, requirements, what each patch
    fixed and when. Use for "did the developers…" questions.

    Args:
        query: What to look for, e.g. "save corruption fix".
        top_k: How many documents to return (default 3).

    Returns:
        dict: status, and hits with file, score (0-1), and text.
    """
    vectors, meta = _doc_index()
    q = _embed(query, task_type="RETRIEVAL_QUERY")[0]
    scores = vectors @ q
    top = np.argsort(scores)[::-1][:top_k]

    hits = [
        {
            "file": meta[int(i)]["file"],
            "score": round(float(scores[int(i)]), 3),
            "text": meta[int(i)]["text"],
        }
        for i in top
    ]
    return {"status": "success", "hits": hits}


# --------------------------------------------------------------------------
# Part 4 — the loop-exit tool
# --------------------------------------------------------------------------

def exit_loop(tool_context: ToolContext) -> None:
    """Call this ONLY when the critique says the report needs no further changes.

    Signals that the quality loop is finished.
    """
    # Returning None (not {}) matters: a non-empty-ish return would be echoed
    # as text on the exit event — and the reviser's output_key would save that
    # echo over the approved report_draft.
    print(f"  ⏹  exit_loop called by {tool_context.agent_name} — report approved")
    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
