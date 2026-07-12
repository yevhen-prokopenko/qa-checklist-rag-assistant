"""End-to-end RAG brain — validate in TERMINAL before building UI (step 4).

Usage:
    python rag_pipeline.py            # runs on the held-out demo task
Prints suggested items to add as a table so you can judge retrieval+
generation quality before wrapping it in the Chrome extension.

Demo task lives in ../data/demo_tasks/KAN-11.json (single source of
truth — edit the JSON to change the scenario, not this file).
"""
import json
import os
import db
import retrieval
import llm

DEMO_TASK_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "demo_tasks", "KAN-11.json"
)


def load_demo_task(path=DEMO_TASK_FILE):
    data = json.load(open(path, encoding="utf-8"))
    return data["task"], data["tester_checklist"], data.get("domain")


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation and extra spaces for fuzzy comparison."""
    import re
    text = text.lower()
    # Remove the "— why ..." tail that gets appended on apply
    text = re.sub(r"\s*[—–-]+\s*.+$", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _is_duplicate(suggestion_item: str, existing: list[str], threshold: float = 0.80) -> bool:
    """Return True if suggestion is too similar to any existing checklist item."""
    from difflib import SequenceMatcher
    norm_s = _normalise(suggestion_item)
    for existing_item in existing:
        norm_e = _normalise(existing_item)
        ratio = SequenceMatcher(None, norm_s, norm_e).ratio()
        if ratio >= threshold:
            return True
    return False


def run(task_text, tester_checklist, domain=None):
    conn = db.connect()
    retrieved = retrieval.retrieve(conn, task_text, domain=domain)
    conn.close()

    print(f"\nRetrieved {len(retrieved)} past cases:")
    for r in retrieved:
        print(f"  - {r['source_key']} ({r['domain']}) score={r['score']:.2f}")

    suggestions = llm.generate_suggestions(task_text, tester_checklist, retrieved)

    # Clean curly braces from suggestions
    for s in suggestions:
        item = s.get("item", "").strip()
        if item.startswith("{{") and item.endswith("}}"):
            s["item"] = item[2:-2].strip()

    # Deduplicate: drop suggestions too similar to what's already in the checklist
    before = len(suggestions)
    suggestions = [
        s for s in suggestions
        if not _is_duplicate(s.get("item", ""), tester_checklist)
    ]
    dropped = before - len(suggestions)
    if dropped:
        print(f"[dedup] Dropped {dropped} suggestion(s) already covered by checklist.")

    print("\n" + "=" * 70)
    print(f"{'Checklist item':40} | Why")
    print("-" * 70)
    for s in suggestions:
        print(f"{s.get('item','')[:40]:40} | {s.get('why','')}")
    print("=" * 70)
    return suggestions


if __name__ == "__main__":
    # NOTE: domain is intentionally NOT passed as a hard filter here.
    # A hard `WHERE domain = ...` would exclude genuinely relevant
    # cross-domain cases (e.g. multi-warehouse routing, conveyor rollback)
    # before semantic similarity even gets to compare them — defeating the
    # point of RAG. Domain stays available as metadata / an optional filter
    # for callers who explicitly want to narrow the search.
    task_text, tester_checklist, _domain = load_demo_task()
    run(task_text, tester_checklist, domain=None)
