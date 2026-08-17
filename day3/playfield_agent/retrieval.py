"""Day 3, Part 3 — RAG over the Playfield docs corpus.

data/docs/ holds 40 markdown files: a store page and dated patch notes for each
game. Reviews tell you what players FEEL; these docs are the closest thing to
ground truth about what the games ARE and what the developers actually shipped.

Index design (deliberately simple): one embedding per FILE. Our docs are small,
so file-level retrieval works. Real corpora need chunking — splitting long
documents into overlapping pieces — same pipeline, one extra step.

Build (or rebuild) the index explicitly with:

    python -m playfield_agent.retrieval
"""

import functools
import json
from pathlib import Path

import numpy as np

from .tools import _embed, repo_root

INDEX_DIR = Path(__file__).resolve().parent.parent / "cache"
VECTORS_FILE = INDEX_DIR / "doc_vectors.npy"
META_FILE = INDEX_DIR / "doc_meta.json"


def build_index() -> int:
    """Embed every file in data/docs/ and cache vectors + metadata. Returns doc count."""
    docs_dir = repo_root() / "data" / "docs"
    paths = sorted(docs_dir.glob("*.md"))
    if not paths:
        raise RuntimeError(f"No docs found in {docs_dir}")

    texts = [p.read_text(encoding="utf-8") for p in paths]
    print(f"Embedding {len(paths)} docs…")
    vectors = _embed(texts, task_type="RETRIEVAL_DOCUMENT")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS_FILE, vectors)
    META_FILE.write_text(
        json.dumps([{"file": p.name, "text": t} for p, t in zip(paths, texts)]),
        encoding="utf-8",
    )
    return len(paths)


@functools.lru_cache(maxsize=1)
def _index() -> tuple[np.ndarray, list[dict]]:
    if not VECTORS_FILE.exists():
        build_index()
    return np.load(VECTORS_FILE), json.loads(META_FILE.read_text(encoding="utf-8"))


def search_docs(query: str, top_k: int = 3) -> dict:
    """Searches Playfield's official docs: store pages and dated patch notes.

    This is the source of truth for FACTS: features, system requirements, what
    each patch fixed and when. Use it for any question about fixes, updates,
    versions, or "did the developers…". (Player opinions live in
    search_reviews, not here.)

    Args:
        query: What to look for, e.g. "save corruption fix" or
            "Neon Drift Racers system requirements".
        top_k: How many documents to return (default 3).

    Returns:
        dict: status, and a list of hits with file (e.g. 'g12-patch-notes.md'),
        score (0-1 relevance), and the document text.
    """
    # TODO(you): Part 3, step 3.2 — same shape as search_reviews:
    #   1. vectors, meta = _index()
    #   2. q = _embed(query, task_type="RETRIEVAL_QUERY")[0]
    #   3. scores = vectors @ q ; top = np.argsort(scores)[::-1][:top_k]
    #   4. hits = [{"file": meta[i]["file"], "score": round(float(scores[i]), 3),
    #               "text": meta[i]["text"]} for i in top]
    #   5. return {"status": "success", "hits": hits}

    vectors, meta = _index()
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


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} docs → {VECTORS_FILE.relative_to(repo_root())}")
