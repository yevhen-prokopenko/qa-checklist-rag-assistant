"""Minimal local API the Chrome extension calls.

Run:  uvicorn api:app --reload --port 8000

Jira credentials (JIRA_BASE_URL/EMAIL/API_TOKEN) live only in backend/.env —
they never touch the browser extension. The extension only sends an issue
key; this backend does all Jira + LLM calls server-side.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import rag_pipeline
import jira_client
import checklist_parser
import embeddings
import db

app = FastAPI(title="RAG Checklist Assistant")

# Allow the extension (any origin for local demo).
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class SuggestRequest(BaseModel):
    task_text: str
    tester_checklist: list[str]
    domain: str | None = None


class SuggestFromJiraRequest(BaseModel):
    issue_key: str


class AppliedItem(BaseModel):
    item: str
    why: str


class ApplyToJiraRequest(BaseModel):
    issue_key: str
    task_text: str
    tester_checklist: list[str] = []   # tester's own items (provenance 🧑)
    ai_applied: list[str] = []         # AI items already in the description from previous runs
    applied_items: list[AppliedItem]   # newly accepted AI suggestions (provenance 🤖)


class WriteTemplateRequest(BaseModel):
    issue_key: str
    template: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/suggest")
def suggest(req: SuggestRequest):
    """Used by terminal validation (rag_pipeline.py) and for direct testing —
    task text and checklist are passed explicitly, no Jira involved."""
    suggestions = rag_pipeline.run(req.task_text, req.tester_checklist, req.domain)
    return {"suggestions": suggestions}


@app.post("/suggest-from-jira")
def suggest_from_jira(req: SuggestFromJiraRequest):
    """Extension entry point: reads the issue via Jira REST API (robust vs.
    DOM scraping), extracts the tester's checklist from the description,
    and runs the RAG pipeline. Returns a clear error if no checklist section
    is found — never silently proceeds with an empty checklist."""
    try:
        issue = jira_client.get_issue(req.issue_key)
    except Exception as e:
        return {"error": f"Could not fetch issue from Jira: {e}"}

    checklist_data = checklist_parser.extract_checklist(issue["description"])
    if not checklist_data:
        template = (
            "|| Human/AI || QA Checklist || Tested on TestEnv? || Tested on ProdEnv? ||\n"
            "| | 1. Verification Point 1 | [ ] | [ ] |\n"
            "| | 2. Verification Point 2 | [ ] | [ ] |"
        )
        return {
            "error": "Checklist not found / empty format. Add the QA Checklist table to the description.",
            "template": template
        }

    tester_checklist = checklist_data["tester"]
    ai_applied = checklist_data["ai"]
    # For RAG we pass both tester and AI-applied items as "current coverage"
    # so the LLM won't re-suggest things already in the checklist
    full_checklist = tester_checklist + ai_applied

    task_text = f"{issue['key']}: {issue['summary']}\n\n{issue['description']}"
    if issue.get("parent_key"):
        try:
            parent = jira_client.get_issue(issue["parent_key"])
            task_text += f"\n\n[Parent {parent['key']}] {parent['summary']}\n{parent['description']}"
        except Exception:
            pass  # parent context is a nice-to-have, not required

    suggestions = rag_pipeline.run(task_text, full_checklist, domain=None)
    return {
        "issue_key": issue["key"],
        "tester_checklist": tester_checklist,
        "ai_applied": ai_applied,
        "suggestions": suggestions
    }


@app.post("/apply-to-jira")
def apply_to_jira(req: ApplyToJiraRequest):
    """Writes the final checklist back to the issue as a comment (v2 API accepts
    plain text — simpler/safer than rewriting the ADF description via v3), with
    PROVENANCE tags: 🧑 = written by the tester, 🤖 = accepted AI suggestion.

    This marks the ARTIFACT's origin (transparency/traceability so a reviewer
    knows what to scrutinize), NOT the person — we deliberately do not aggregate
    this into any per-tester "reliance on AI" scoring (see design notes in
    04_Demo_Scenario.md).

    Also feeds the approved final checklist into the knowledge base (self-learning,
    step 6 — quality-gated: only what a human explicitly kept/approved). Stored
    text is clean (no emoji tags) so retrieval stays accurate."""
    table_lines = [
        "|| Human/AI || QA Checklist || Tested on TestEnv? || Tested on ProdEnv? ||"
    ]
    idx = 1
    # 1. Tester's own items
    for item in req.tester_checklist:
        table_lines.append(f"| 🧑 | {idx}. {item} | [ ] | [ ] |")
        idx += 1
    # 2. AI items already applied in previous runs — preserve provenance
    for item in req.ai_applied:
        table_lines.append(f"| 🤖 | {idx}. {item} | [ ] | [ ] |")
        idx += 1
    # 3. Newly accepted AI suggestions from this run
    for i in req.applied_items:
        table_lines.append(f"| 🤖 | {idx}. {i.item} — {i.why} | [ ] | [ ] |")
        idx += 1

    final_table = "\n".join(table_lines)
    try:
        jira_client.update_description(req.issue_key, final_table)
    except Exception as e:
        return {"error": f"Could not update Jira ticket: {e}"}

    # Self-learning: feed only the newly applied items back into the knowledge base
    # (ai_applied items were already stored in previous runs)
    new_items = [i.item for i in req.applied_items]
    if new_items:
        conn = db.connect()
        for item in new_items:
            chunk = f"[Task] {req.task_text}\n[Checklist item] {item}"
            vec = embeddings.embed_one(chunk)
            db.insert_knowledge(conn, req.issue_key, None, chunk, vec, approved=True)
        conn.close()

    total = len(req.tester_checklist) + len(req.ai_applied) + len(req.applied_items)
    return {"ok": True, "written_to_jira": total,
            "human": len(req.tester_checklist), "ai": len(req.ai_applied) + len(req.applied_items)}


@app.post("/write-template-to-jira")
def write_template_to_jira(req: WriteTemplateRequest):
    try:
        jira_client.update_description(req.issue_key, req.template)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
