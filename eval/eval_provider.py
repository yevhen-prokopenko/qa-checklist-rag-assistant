"""Custom Promptfoo Python Provider for RAG Checklist Assistant.
Directly calls the application's backend pipeline (backend/rag_pipeline.py)
and formats the final output with Human (🧑) and AI (🤖) provenance tags, matching Jira.
"""
import os
import sys
import json
from dotenv import load_dotenv

# Add backend to sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Load environment variables from backend/.env
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

import rag_pipeline


def call_api(prompt, options, context):
    """
    Promptfoo custom provider entrypoint.
    Receives test case variables from context['vars'], executes rag_pipeline.run(),
    and formats the output as a full Jira-like Provenance table (🧑 Human / 🤖 AI).
    """
    try:
        vars_dict = context.get("vars", {}) if context else {}
        task_text = vars_dict.get("input_task", "")
        
        # Parse tester draft into a list of checklist items
        tester_draft_raw = vars_dict.get("tester_draft", "")
        if isinstance(tester_draft_raw, list):
            tester_checklist = tester_draft_raw
        elif "\n" in tester_draft_raw:
            tester_checklist = [
                line.strip().lstrip("-*123456789. ")
                for line in tester_draft_raw.splitlines()
                if line.strip()
            ]
        elif ";" in tester_draft_raw:
            tester_checklist = [
                item.strip() for item in tester_draft_raw.split(";") if item.strip()
            ]
        else:
            tester_checklist = [tester_draft_raw.strip()] if tester_draft_raw.strip() else []

        domain = vars_dict.get("domain", None)

        # Run real RAG pipeline
        suggestions = rag_pipeline.run(task_text, tester_checklist, domain=domain)

        # Build full Markdown table matching Jira format with Provenance (🧑 / 🤖)
        table_lines = [
            "### 📋 Final Applied Checklist (Jira Provenance View)",
            "",
            "| Human/AI | QA Checklist Item | Why / Reason |",
            "|:---:|---|---|"
        ]
        
        idx = 1
        # 1. Tester's original items (🧑 Human)
        for item in tester_checklist:
            table_lines.append(f"| 🧑 Human | {idx}. {item} | *(Authored by tester)* |")
            idx += 1
            
        # 2. AI suggested items (🤖 AI)
        for s in suggestions:
            item_text = s.get("item", "")
            why_text = s.get("why", "")
            table_lines.append(f"| 🤖 AI | {idx}. {item_text} | {why_text} |")
            idx += 1

        formatted_table = "\n".join(table_lines)
        
        # Return markdown output for Promptfoo UI rendering and evaluation
        return {
            "output": formatted_table
        }
    except Exception as e:
        return {
            "error": f"RAG Pipeline execution error: {str(e)}"
        }
