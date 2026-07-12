"""Helper script to upload mock tasks to Jira sandbox."""
import json
import glob
import os
import requests
from requests.auth import HTTPBasicAuth
import config

def parse_task(item):
    source_key = item.get("source_key", "")
    task_text = item.get("task", "").strip()
    
    # Split summary and description
    parts = task_text.split(". ", 1)
    summary_part = parts[0]
    desc_part = parts[1] if len(parts) > 1 else ""
    
    # If summary_part already has the key, use it as is, otherwise prefix
    if ":" in summary_part:
        summary = summary_part
    else:
        summary = f"{source_key}: {summary_part}"
        
    description = desc_part
    if description:
        description += "\n\n"
    
    domain = item.get("domain")
    if domain:
        description += f"Domain: {domain}\n\n"
        
    checklist = item.get("checklist", [])
    if "tester_checklist" in item:
        checklist = item.get("tester_checklist", [])
            
    return summary, description, checklist

def create_issue(summary, description, parent_key=None):
    url = f"{config.JIRA_BASE_URL}/rest/api/2/issue"
    fields = {
        "project": {
            "key": "KAN"
        },
        "summary": summary,
        "description": description,
    }
    if parent_key:
        fields["parent"] = {"key": parent_key}
        fields["issuetype"] = {"name": "Subtask"}
    else:
        fields["issuetype"] = {"name": "Feature"}
        
    payload = {"fields": fields}
    resp = requests.post(
        url,
        json=payload,
        auth=HTTPBasicAuth(config.JIRA_EMAIL, config.JIRA_API_TOKEN),
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()

def main():
    # 1. Historical tasks
    knowledge_dir = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge")
    files = sorted(glob.glob(os.path.join(knowledge_dir, "*.json")))
    
    # 2. Demo task
    demo_dir = os.path.join(os.path.dirname(__file__), "..", "data", "demo_tasks")
    files += sorted(glob.glob(os.path.join(demo_dir, "*.json")))
    
    print(f"Found {len(files)} files to populate.")
    
    for f in files:
        if "PLACEHOLDER" in f:
            continue
        try:
            with open(f, encoding="utf-8") as file:
                item = json.load(file)
            summary, description, checklist = parse_task(item)
            
            # 1. Create Feature (Parent)
            res = create_issue(summary, description)
            parent_key = res['key']
            print(f"Created Feature: {parent_key} for source_key: {item.get('source_key')} | Summary: {summary}")
            
            # 2. Create QA Subtask (Child)
            if checklist:
                is_demo = (item.get("source_key") == "KAN-11" or "tester_checklist" in item)
                sub_summary = f"[QA] {summary}"
                if is_demo:
                    sub_desc = ""
                else:
                    table_lines = [
                        "|| Human/AI || QA Checklist || Tested on TestEnv? || Tested on ProdEnv? ||"
                    ]
                    for idx, line in enumerate(checklist, 1):
                        table_lines.append(f"| | {idx}. {line} | [ ] | [ ] |")
                    sub_desc = "\n".join(table_lines)
                sub_res = create_issue(sub_summary, sub_desc, parent_key=parent_key)
                print(f"  Created Subtask: {sub_res['key']} under {parent_key}")
        except Exception as e:
            print(f"Error creating issue for {f}: {e}")

if __name__ == "__main__":
    main()
