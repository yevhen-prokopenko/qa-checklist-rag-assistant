"""Jira REST API client.

Uses API v2 deliberately (not v3): v2 returns `description` as plain
text/wiki-markup, while v3 returns Atlassian Document Format (ADF) JSON,
which is much harder to parse for a simple bullet-list checklist. This
keeps checklist_parser.py trivial. Reading data via API (not DOM scraping)
is robust against Jira layout/theme changes.
"""
import requests
from requests.auth import HTTPBasicAuth
import config


def _auth():
    return HTTPBasicAuth(config.JIRA_EMAIL, config.JIRA_API_TOKEN)


def get_issue(issue_key):
    url = f"{config.JIRA_BASE_URL}/rest/api/2/issue/{issue_key}"
    resp = requests.get(
        url, params={"fields": "summary,description,parent,subtasks"}, auth=_auth(), timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    fields = data.get("fields", {})
    parent = fields.get("parent")
    subtasks = fields.get("subtasks", [])
    subtask_keys = [st.get("key") for st in subtasks if st.get("key")]
    return {
        "key": data.get("key"),
        "summary": fields.get("summary") or "",
        "description": fields.get("description") or "",
        "parent_key": parent.get("key") if parent else None,
        "subtask_keys": subtask_keys,
    }


def add_comment(issue_key, body_text):
    url = f"{config.JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    resp = requests.post(url, json={"body": body_text}, auth=_auth(), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_comments(issue_key):
    url = f"{config.JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    resp = requests.get(url, auth=_auth(), timeout=10)
    resp.raise_for_status()
    return resp.json().get("comments", [])


def delete_comment(issue_key, comment_id):
    url = f"{config.JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment/{comment_id}"
    resp = requests.delete(url, auth=_auth(), timeout=10)
    resp.raise_for_status()


def update_description(issue_key, new_description):
    url = f"{config.JIRA_BASE_URL}/rest/api/2/issue/{issue_key}"
    resp = requests.put(
        url, json={"fields": {"description": new_description}}, auth=_auth(), timeout=10
    )
    resp.raise_for_status()
