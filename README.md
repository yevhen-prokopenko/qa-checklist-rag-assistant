# RAG Checklist Assistant

A Chrome extension + RAG backend that helps QA testers write more complete test checklists — grounded in the team's own past verified cases, not generic AI guessing.

> **Status: demo / proof-of-concept.** Built on fully anonymized, fictional test data to demonstrate the algorithm and design decisions — not to expose any real company's code, tasks, or confidential information. See [Honest framing](#honest-framing) below.

---

## The problem

Testers miss edge cases — not because they lack skill, but because no single person can hold a team's entire accumulated experience in their head. Knowledge about past bugs, rollbacks, race conditions and other nuances lives in senior people's heads and gets lost when passed on to newcomers. The result: inconsistent checklist quality, repeated misses, and slow onboarding.

## The approach

A RAG-based assistant that plugs into Jira:

1. **Tester writes their own checklist first.** No checklist → no AI. The tool never generates tests from a blank page — it augments human thinking, it doesn't replace it (see [Design decision 1](#1-write-first-gate-anti-deskilling)).
2. **The system retrieves similar past verified checklists** from a knowledge base of previously completed QA tasks, using semantic search (vector embeddings, not keyword match).
3. **An LLM reads the tester's checklist + the retrieved past cases** and suggests concrete items to add — each with a **"why"** explaining which past case it's grounded in. If nothing's missing, it says so.
4. **The tester picks what's relevant** and applies it. The final checklist is written back to Jira with **provenance tags** (🧑 human-written / 🤖 AI-suggested) — transparent, but never scored against the person (see [Design decision 2](#2-provenance-not-surveillance)).
5. **Accepted suggestions feed back into the knowledge base** (self-learning) — quality-gated: only what a human explicitly kept.

One line: *tester writes → RAG retrieves relevant past cases → LLM suggests what's missing, with reasons → human decides → system remembers.*

---

## Architecture (brief)

```
Jira issue (task + tester's checklist)
        │
        ▼
  Embed task text (OpenAI text-embedding-3-small)
        │
        ▼
  Vector search in Postgres/pgvector (cosine similarity, top-20)
        │
        ▼
  Diversify (max 2 chunks per source — no single past task dominates)
        │
        ▼
  LLM (gpt-4o-mini) reads checklist + top-5 past cases → suggests items to add + why (or nothing, if the checklist is already complete)
        │
        ▼
  Dedup against existing checklist (fuzzy match)
        │
        ▼
  Tester reviews, applies selected → written back to Jira with 🧑/🤖 provenance
        │
        ▼
  Newly accepted items → embedded → added to knowledge base
```

Full technical deep-dive — indexing + query pipelines as Mermaid diagrams, chunking rationale, DB schema, parameters: **[ARCHITECTURE.md](./ARCHITECTURE.md)**.

---

## Design decisions

### 1. Write-first gate (anti-deskilling)

The tool refuses to run on an empty checklist — it returns an error and a ready-to-fill template instead of generating tests from scratch. This is a deliberate choice: if the AI wrote checklists unprompted, testers would stop thinking for themselves over time. The tester writes first; the AI augments second. In a real product this hard gate would likely soften into a nudge or a two-mode system (`assist` vs `scaffold`, with senior review required for the latter) — but for a demo, the hard gate makes the philosophy visible.

### 2. Provenance, not surveillance

Every checklist item written back to Jira is tagged 🧑 (human) or 🤖 (AI-suggested-and-accepted). This is industry-standard transparency (TestRail/Xray/Zephyr tag AI-generated content the same way; Copilot does `Co-authored-by`). The deliberate boundary: **the tag marks the artifact's origin, never the person.** It is never aggregated into a per-tester "reliance on AI" score — that would turn a transparency tool into a surveillance tool, which was a hard line from the start.

### 3. A real bug, found and fixed: the domain filter

Early on, retrieval for a "transfer to a closing warehouse" task returned five chunks from the *same* single past case — semantically related tasks in other domains (multi-warehouse routing, conveyor rollback logic) never showed up. Adding result diversification didn't fix it. The actual cause: a hard `WHERE domain = 'wms-transfer'` filter in the SQL query excluded cross-domain candidates *before* vector similarity ever got to compare them — defeating the entire point of semantic search, which is to find relevance across category boundaries. Removing the hard filter (keeping domain as metadata only) fixed it: retrieval now pulls from all three genuinely relevant past cases.

### 4. Multi-round, not one-shot

The checklist table in Jira distinguishes 🧑 tester items from 🤖 already-accepted AI items. This means the tool can be run again after an Apply — it won't re-suggest what was already accepted, because it reads its own prior output back as context.

---

## Quick start

```bash
cd rag_checklist
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

docker compose up -d               # Postgres + pgvector on localhost:5434

cp backend/.env.example backend/.env    # fill in OpenAI key + Jira creds

cd backend
python ingest.py                   # index data/knowledge/*.json into pgvector
python rag_pipeline.py             # sanity-check the RAG core in the terminal — no Jira needed here

uvicorn api:app --reload --port 8000    # backend for the extension
```

Load the extension: `chrome://extensions` → Developer mode → Load unpacked → select `extension/`.

To re-run the full demo scenario from a clean slate (knowledge base + Jira comments + the demo subtask's checklist, all reset): `python reset_demo.py`.

**Note on the full Jira flow:** `backend/populate_jira.py` (creates the KB tasks + demo task in Jira) is tied to the specific Jira Cloud project this demo was built against — a project keyed `KAN`, with a custom `Feature` issue type alongside the default `Subtask`. It's included for transparency (this is genuinely how the sandbox was set up), not as a one-command setup for an arbitrary Jira instance. The `ingest.py` + `rag_pipeline.py` steps above are fully self-contained and don't require Jira at all — they're the fastest way to see the RAG core work end to end.

### Jira checklist format

Open the **QA subtask** (child of a Feature, e.g. `KAN-22` under `KAN-11`) — the checklist lives there, not on the parent. Two supported formats in the subtask's description:

**Bullets** (for writing a checklist from scratch):
```
h3. QA Checklist
* Create transfer to an open warehouse
* Check transfer appears in destination inbound list
```

**Table with provenance** (what the tool writes after Apply, and what it now hands you as a ready template on an empty checklist):
```
|| Human/AI || QA Checklist || Tested on TestEnv? || Tested on ProdEnv? ||
| 🧑 | 1. Create transfer to an open warehouse | [ ] | [ ] |
| 🤖 | 2. Rollback on rejection — why: ... | [ ] | [ ] |
```

If the checklist is missing or empty, the extension shows a clear error and a template you can insert with one click (`/write-template-to-jira`) — it never proceeds silently on empty input.

---

## Evaluation (Promptfoo)

Building the tool is only half the job. The other half is proving it does what it claims, since LLM output is not deterministic and cannot be checked with a simple equality assertion.

**Held-out evaluation.** Tasks `KAN-1` to `KAN-10` are indexed in the knowledge base. `KAN-11` is deliberately kept out of the index. This is not about the system having no data: it still retrieves from the same knowledge base as always. It is about preventing data leakage. If `KAN-11` were indexed too, the system could retrieve a near-identical match of itself and pass the test by lookup, not by generalizing patterns from related but different past cases (`KAN-7` transfers, `KAN-3` routing, `KAN-1` rollback logic).

**Parity with the real app.** The Promptfoo test runner does not call the LLM with a hardcoded copy of the prompt. A custom Python provider (`eval/eval_provider.py`) imports and calls the same `rag_pipeline.run()` function the Chrome extension uses. Any prompt change in `backend/llm.py` is automatically covered by the next eval run, and the eval results reflect exactly what a tester would see in Jira.

**What's tested.** Nine scenarios across three categories:
- functional: does the assistant fill gaps in a thin draft, avoid duplicating what the tester already wrote, stay silent when the draft is already complete, and handle informal phrasing
- out-of-scope traps: does it ignore fictional, non-WMS content injected into the input instead of inventing checks for it
- redteam and security: does it resist prompt injection (instructions to reveal its system prompt or write something unrelated) and refuse destructive instructions (dropping tables, deleting audit logs)

Grading combines deterministic checks (schema, duplication) with an LLM-as-judge rubric for the parts that cannot be checked with equality: completeness and groundedness.

Details: [15_Test_Design_for_RAG_System.md](./15_Test_Design_for_RAG_System.md), [16_Golden_Dataset_Scenarios_KAN11.md](./16_Golden_Dataset_Scenarios_KAN11.md), code in [eval/](./eval/).

---

## Honest framing

This is a **demo / proof-of-concept**, not a production system. The idea originated from a real QA pain point encountered at work; everything you see here — the Jira tasks, the checklists, the "past cases" the RAG retrieves from — was **rebuilt from scratch on fictional, anonymized data**. No real company code, task descriptions, or confidential information is used. It's realistic enough to demonstrate the full algorithm end to end, and no more than that.

---

## Possible extensions (not implemented)

Two things worth naming as deliberate scope decisions, not oversights:

- **Hybrid search (vector + BM25 keyword matching).** Pure vector search can miss exact terms — error codes, IDs, specific field names — that keyword matching catches reliably. `rank-bm25` is already in `requirements.txt` as a placeholder for this.
- **Reranking.** Retrieve a wider candidate pool (e.g. top-30), then re-score with a cross-encoder before picking the final top-5 — trades a bit of latency for retrieval precision.

Neither was needed at this project's scale (10 knowledge-base tasks) to prove the algorithm — both are the standard next step once a knowledge base grows into the thousands of entries.

---

## What's in this repo

- `backend/` — Python: config, DB schema (pgvector), embeddings (OpenAI API), ingest, retrieval + diversification, generation (RAG core), Jira REST client, FastAPI server for the extension. `backend/_archive/` holds one-off migration scripts used while building this (not part of the running system).
- `extension/` — Chrome extension (Manifest V3): button injected into the Jira issue view, in-page modal, background service worker.
- `data/knowledge/` — the 10 "past verified" QA tasks the RAG learns from (fictional, anonymized). `data/demo_tasks/` — the held-out task used for the live demo.
- `docker-compose.yml` — Postgres + pgvector.
- `eval/` — Promptfoo evaluation harness: custom provider, golden dataset, functional/out-of-scope/redteam test configs.

---

## 📚 Project documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — technical deep-dive: indexing + query pipelines, Mermaid diagrams, DB schema, parameters.
- **[15_Test_Design_for_RAG_System.md](./15_Test_Design_for_RAG_System.md)** — evaluation strategy, failure modes, test fidelity.
- **[16_Golden_Dataset_Scenarios_KAN11.md](./16_Golden_Dataset_Scenarios_KAN11.md)** — the 9 golden dataset test cases in detail.
