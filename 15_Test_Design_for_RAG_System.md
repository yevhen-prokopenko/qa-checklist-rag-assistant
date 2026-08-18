# 15. Test Design & Evaluation Strategy for RAG Assistant

## 1. Goal
Design a robust evaluation and testing harness for the **QA RAG Assistant** using `promptfoo`. The system operates as an **AI Copilot / Reviewer** for QA engineers. It is not designed to generate test cases from a blank slate; instead, it analyzes a preliminary draft written by a human tester and suggests missing edge cases and safety checks based on a verified Knowledge Base (KB) of past production incidents.

---

## 2. Key Risks & Failure Modes
The evaluation harness is designed to detect and measure four primary failure modes common to RAG systems:

1. **Faithfulness / Hallucination:** The assistant invents checks or technical assertions that have no grounding in the indexed Knowledge Base.
2. **Recall / Completeness:** The assistant fails to retrieve and recommend critical edge cases that exist in past verified cases.
3. **Relevance / Deduplication:** The assistant suggests irrelevant checks from unrelated domains or duplicates checks already written by the human tester.
4. **Instruction Following & Format:** The assistant fails to adhere to structural constraints (e.g., returning valid JSON with `item` and `why` justifications, or preserving table provenance).

---

## 3. Input Constraints & Scenarios
By design, the application enforces a **write-first policy** (empty checklist submissions are blocked to prevent human cognitive offloading). The Golden Dataset simulates realistic tester behaviors and draft states:

* **Scenario A: Thin / Basic Draft (Most Frequent):**
  * *Context (`KAN-11`):* `WMS-1400: Transfer stock to a destination warehouse that is mid-closure.`
  * *Tester Draft:* Basic happy-path creation and listing.
  * *Expected Output:* RAG supplements the draft with missing edge cases: Rollback on destination rejection, Re-routing when closed, Partial transfer logic, and Audit logging.
* **Scenario B: Deduplication on Partial Drafts:**
  * *Tester Draft:* Tester already included a check for Rollback or Re-route.
  * *Expected Output:* RAG must supplement other missing checks while **strictly avoiding duplicate suggestions** for the already covered topic.
* **Scenario C: Full Coverage / Senior Tester:**
  * *Tester Draft:* All 6 necessary checks are already covered.
  * *Expected Output:* RAG returns an empty list (`[]` / `NOTHING TO ADD`), avoiding unnecessary noise or over-generation.
* **Scenario D: Informal / Colloquial Input:**
  * *Tester Draft:* Abbreviated slang (`1 make transfer to open wh; 2 check dest inbound`).
  * *Expected Output:* Semantic normalization and grounded professional recommendations.

> **Design Constraint Note:** The system prompt in `backend/llm.py` explicitly enforces `"never suggest removing or rewriting what the tester already has"`. The assistant serves strictly as an additive reviewer.

---

## 4. Architecture & 100% Test Parity
To ensure that automated evaluation accurately mirrors production behavior without the overhead of maintaining duplicate prompts:

* **Zero Prompt Duplication:** `promptfooconfig.yaml` does not hardcode a secondary copy of the LLM prompt.
* **Custom Python Provider (`eval_provider.py`):** Promptfoo calls a Python bridge that directly executes the application's actual backend pipeline (`backend/rag_pipeline.py`).
* **100% In-Memory Parity:** Because Promptfoo and the Chrome extension / Jira API invoke the exact same Python function with identical vector search parameters (`pgvector`), test fidelity is mathematically guaranteed. Any modification to `llm.py` or `rag_pipeline.py` is immediately reflected in the evaluation suite.

---

## 5. Architectural Separation of Responsibilities
* **Promptfoo Evaluation Harness (In-Memory Engine):** Evaluates the core AI brain—semantic correctness, retrieval recall, deduplication logic, and security guardrails—using deterministic assertions and LLM-as-a-judge rubrics.
* **Chrome Extension & FastAPI Layer:** Provides the UI integration, handling Jira Document Format (ADF) parsing, user provenance tags (`🧑 Human` / `🤖 AI`), and Jira REST API synchronization (`/apply-to-jira`).
