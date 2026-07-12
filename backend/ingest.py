"""Ingest past verified checklists into the RAG store.

Data format (data/knowledge/*.json), each file = one past task:
{
  "source_key": "QA-1201",
  "domain": "wms-transfer",
  "task": "Short task/TЗ description ...",
  "checklist": ["check 1", "check 2", ...],
  "approved": true
}

TODO(Eugene): drop 5-10 such fake historical files into data/knowledge/
(we will generate them together once you give the domain context).
"""
import json
import glob
import os
import db
import embeddings

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge")


def chunk_checklist(item):
    """Structural chunking: one chunk = task summary + one checklist line.
    Keeps each vector focused (best practice vs dumping the whole doc)."""
    task = item.get("task", "").strip()
    chunks = []
    for line in item.get("checklist", []):
        line = line.strip()
        if line:
            chunks.append(f"[Task] {task}\n[Checklist item] {line}")
    return chunks


def main():
    files = glob.glob(os.path.join(KNOWLEDGE_DIR, "*.json"))
    if not files:
        print(f"No knowledge files in {KNOWLEDGE_DIR}. Add fake historical tasks first.")
        return
    conn = db.connect()
    # Idempotent: wipe first so re-running ingest rebuilds a clean KB (no
    # duplicates, no leftover self-learning rows from a previous demo run).
    before = db.count_knowledge(conn)
    db.reset_knowledge(conn)
    print(f"Reset knowledge table (was {before} rows).")
    total = 0
    for f in files:
        item = json.load(open(f, encoding="utf-8"))
        chunks = chunk_checklist(item)
        if not chunks:
            continue
        vectors = embeddings.embed_texts(chunks)
        for chunk, vec in zip(chunks, vectors):
            db.insert_knowledge(
                conn, item.get("source_key"), item.get("domain"),
                chunk, vec, item.get("approved", True),
            )
            total += 1
        print(f"  ingested {len(chunks)} chunks from {os.path.basename(f)}")
    conn.close()
    print(f"Done. {total} chunks ingested.")


if __name__ == "__main__":
    main()
