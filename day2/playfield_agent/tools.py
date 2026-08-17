"""Playfield analyst tools — Day 2 scaffold.

Parts 2-3 of the walkthrough happen in this file. The plumbing (data loading,
embedding calls, caching) is provided; the tools marked TODO are yours — you
already wrote their logic in the Day-1 notebooks, today you package it so an
agent can call it.

Remember: for a tool, the DOCSTRING IS THE USER INTERFACE. The model never sees
your code — it sees the function name, the parameter names/types, and this
docstring, and decides from those alone when (and how) to call it.
"""

import functools
import time
from pathlib import Path

import numpy as np
import pandas as pd
from google import genai
from google.genai import types

GEN_MODEL = "gemini-3.5-flash-lite"
EMBED_MODEL = "gemini-embedding-001"


# --------------------------------------------------------------------------
# Plumbing (read it, don't rewrite it)
# --------------------------------------------------------------------------

def repo_root() -> Path:
    """Walk upwards until we find the repo root (the folder containing data/)."""
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
    """Embed text(s) → normalized vectors. Retries on rate limits (Day 1, Part 3)."""
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
    """The corpus embeddings from Day 1 — loaded from your notebook's cache,
    or recomputed (once) if the cache is missing."""
    cache_file = repo_root() / "day1" / "cache" / "review_embeddings.npy"
    if cache_file.exists():
        return np.load(cache_file)
    print("Day-1 cache not found — embedding 300 reviews (one-time, ~1 min)…")
    vectors = _embed(_reviews()["review_text"].tolist(), task_type="RETRIEVAL_DOCUMENT")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_file, vectors)
    return vectors


# --------------------------------------------------------------------------
# Part 2 — catalog tools
# --------------------------------------------------------------------------

def list_games() -> dict:
    """Does somenthing"
    """
    stats = _reviews().groupby("game_id")["recommended"].mean().round(2) * 100
    games = _games().copy()
    games["pct_recommended"] = games["game_id"].map(stats)
    return {"status": "success", "games": games.to_dict(orient="records")}


def get_game_details(game_id: str) -> dict:
    """Gets full catalog details and review statistics for one game.

    Args:
        game_id: The game's id, e.g. 'g01'. If you only have a title,
            call list_games first to find the id.

    Returns:
        dict: status, catalog fields (title, genre, price_eur, release_year,
        developer) and review stats (n_reviews, pct_recommended,
        median_hours_played).
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


# --------------------------------------------------------------------------
# Part 3 — your Day-1 power tools (TODO: port them from the notebooks)
# --------------------------------------------------------------------------

def search_reviews(query: str, top_k: int = 5) -> dict:
    """Searches all 300 player reviews by MEANING, not keywords.

    Works in any language. Use this whenever the user asks what players say,
    feel, or complain about. Prefer specific queries ("crashes after updates")
    over vague ones ("problems").

    Args:
        query: What to look for, phrased naturally.
        top_k: How many reviews to return (default 5).

    Returns:
        dict: status, and a list of hits with review_id, title (game),
        recommended, score (0-1 relevance), and review_text.
    """
    # TODO(you): this is Day 1, Part 3 — the 15-line search engine.
    #   1. q = _embed(query, task_type="RETRIEVAL_QUERY")[0]
    #   2. scores = _review_vectors() @ q
    #   3. top = np.argsort(scores)[::-1][:top_k]
    #   4. build the hits list from _reviews().iloc[top]  (columns above)
    #   5. return {"status": "success", "hits": [...]}
    q = _embed(query, task_type="RETRIEVAL_QUERY")[0]
    scores = _review_vectors() @ q
    top = np.argsort(scores)[::-1][:top_k]

    df = _reviews()
    hits = []
    for i in top:
        row = df.iloc[i]
        hits.append(
            {
                "review_id": row["review_id"],
                "title": row["title"],
                "recommended": bool(row["recommended"]),
                "score" : float(scores[int(i)]),
                "review_text": row["review_text"],
            }
        )

    return {"status": "success", "hits": hits}

    raise NotImplementedError("Part 3, step 3.1 — port your Day-1 search here")


def analyze_review(review_id: str) -> dict:
    """Reads one review closely and extracts structured facts from its text.

    Use after search_reviews when you need sentiment, the specific issues
    mentioned, or a sarcasm check for a particular review.

    Args:
        review_id: The review's id, e.g. 'r042' (search_reviews returns these).

    Returns:
        dict: status, sentiment (positive/negative/mixed), issues (list of
        category strings), is_sarcastic (bool), and a one-line summary.
    """
    # TODO(you): this is Day 1, Part 4 — structured extraction.
    #   1. look up the review text by review_id in _reviews()
    #      (return a status="error" dict if the id doesn't exist!)
    #   2. call _client().models.generate_content with
    #      response_mime_type="application/json" and
    #      response_schema=ReviewAnalysis (defined below)
    #   3. r = response.parsed
    #   4. return {"status": "success", "review_id": review_id,
    #              "sentiment": r.sentiment, "issues": [i.value for i in r.issues],
    #              "is_sarcastic": r.is_sarcastic, "summary": r.summary}
    df = _reviews()
    rows = df[df["review_id"] == review_id]
    if rows.empty:
        return {
            "status": "error",
            "message": f"Unknown review_id {review_id!r}. Call search_reviews to find valid ids.",
        }

    response = _client().models.generate_content(
        model=GEN_MODEL,
        contents=f"Analyze this player review:\n\n{rows.iloc[0]['review_text']}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReviewAnalysis,
        ),
    )
    r = response.parsed

    return {
        "status": "success",
        "review_id": review_id,
        "sentiment": r.sentiment,
        "issues": [i.value for i in r.issues],
        "is_sarcastic": r.is_sarcastic,
        "summary": r.summary,
    }


# The schema from Day 1, Part 4 — ready to use in analyze_review.
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class Issue(str, Enum):
    crashes_or_bugs = "crashes_or_bugs"
    performance = "performance"
    difficulty = "difficulty"
    monetization = "monetization"
    content_amount = "content_amount"
    multiplayer_or_netcode = "multiplayer_or_netcode"
    controls_or_ui = "controls_or_ui"
    other = "other"


class ReviewAnalysis(BaseModel):
    sentiment: Literal["positive", "negative", "mixed"]
    issues: list[Issue]
    is_sarcastic: bool
    summary: str
