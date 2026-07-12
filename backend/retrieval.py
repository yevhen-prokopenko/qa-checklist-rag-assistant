"""Retrieval: vector search + optional BM25 hybrid.

For the first validation we use pure vector search (db.search).
Hybrid (BM25) is scaffolded here to add once the vector path works —
per best practices it improves recall on exact terms / IDs.
"""
import db
import embeddings
import config


def diversify(candidates, top_k, max_per_source):
    """Cap chunks per source_key so one document doesn't crowd out others.

    Candidates must already be sorted by score (best first, as returned by
    db.search's ORDER BY). Greedy pass: keep a candidate if its source hasn't
    hit max_per_source yet; stop once top_k results are collected.
    """
    per_source_count = {}
    result = []
    for c in candidates:
        key = c["source_key"]
        if per_source_count.get(key, 0) >= max_per_source:
            continue
        result.append(c)
        per_source_count[key] = per_source_count.get(key, 0) + 1
        if len(result) >= top_k:
            break
    return result


def retrieve(conn, query_text, top_k=config.TOP_K, domain=None,
             max_per_source=config.MAX_PER_SOURCE):
    """Return top-K similar past checklist chunks for a query, diversified
    across sources (over-fetch RETRIEVE_N candidates, then cap per source)."""
    qvec = embeddings.embed_one(query_text)
    candidates = db.search(conn, qvec, top_k=config.RETRIEVE_N, domain=domain)
    return diversify(candidates, top_k=top_k, max_per_source=max_per_source)


# TODO(step 4+): hybrid search
# from rank_bm25 import BM25Okapi
# 1) pull candidate pool via vector search (RETRIEVE_N)
# 2) BM25 over their content vs query tokens
# 3) merge scores (e.g. weighted) -> re-order -> take TOP_K
# Optional: cross-encoder reranker for the final ordering.
