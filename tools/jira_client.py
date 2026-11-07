"""
Jira issue fetch tool.

Connects to a Jira Cloud instance, fetches an issue by key/ID, and
normalizes it into plain text suitable for triage_defect / triage_defect_prompt.

Requires these environment variables (see .env.example):
    JIRA_URL          e.g. https://your-domain.atlassian.net
    JIRA_EMAIL        Jira account email
    JIRA_API_TOKEN    https://id.atlassian.com/manage-profile/security/api-tokens
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

FIELDS = "summary,description,issuetype,status,priority,labels,components,fixVersions,reporter,assignee"


def _flatten_adf(node) -> str:
    """Recursively flatten Atlassian Document Format (ADF) into plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_flatten_adf(item) for item in node)

    text = ""
    if node.get("type") == "text" and isinstance(node.get("text"), str):
        text += node["text"]
    if "content" in node:
        text += _flatten_adf(node["content"])
    if node.get("type") in ("paragraph", "heading", "listItem", "blockquote", "bulletList", "orderedList"):
        text += "\n"
    if node.get("type") in ("hardBreak", "rule"):
        text += "\n"
    return text


def _normalize_issue(raw: dict) -> dict:
    f = raw.get("fields", {}) or {}
    description = f.get("description")
    if isinstance(description, str):
        pass
    elif description:
        description = _flatten_adf(description).strip()
    else:
        description = ""

    return {
        "key": raw.get("key", ""),
        "summary": f.get("summary") or "",
        "description": description,
        "issue_type": (f.get("issuetype") or {}).get("name", "Unknown"),
        "status": (f.get("status") or {}).get("name", "Unknown"),
        "priority": (f.get("priority") or {}).get("name", "Unspecified"),
        "components": [c.get("name") for c in f.get("components", [])],
        "labels": f.get("labels", []),
        "fix_versions": [v.get("name") for v in f.get("fixVersions", [])],
        "reporter": (f.get("reporter") or {}).get("displayName", "Unknown"),
        "assignee": (f.get("assignee") or {}).get("displayName") if f.get("assignee") else None,
    }


def _format_issue_text(issue: dict) -> str:
    lines = [
        f"Key: {issue['key']}",
        f"Summary: {issue['summary']}",
        f"Type: {issue['issue_type']}  |  Status: {issue['status']}  |  Priority: {issue['priority']}",
        f"Components: {', '.join(issue['components']) or 'None'}",
        f"Labels: {', '.join(issue['labels']) or 'None'}",
        f"Reporter: {issue['reporter']}  |  Assignee: {issue['assignee'] or 'Unassigned'}",
        "",
        "Description:",
        issue["description"] or "(no description provided)",
    ]
    return "\n".join(lines)


def _jira_auth():
    """Return (base_url, (email, token)) from env, or an error string."""
    base = (os.environ.get("JIRA_URL") or "").strip().rstrip("/")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_TOKEN")

    if not base:
        return "Error: JIRA_URL is not configured."
    if not email or not token:
        return "Error: JIRA_EMAIL or JIRA_API_TOKEN is not configured."
    return base, (email, token)


def fetch_jira_issue(issue_id: str) -> str:
    """
    Fetch a Jira issue by key (e.g. "QA-123") and return it as formatted
    plain text (summary, status, priority, description, etc.), ready to
    feed into triage_defect or triage_defect_prompt.

    Args:
        issue_id: The Jira issue key or ID, e.g. "QA-123".

    Returns:
        A formatted plain-text summary of the issue, or an error message
        if the issue could not be fetched.
    """
    if not issue_id or not issue_id.strip():
        return "Error: issue_id must not be empty."

    base = (os.environ.get("JIRA_URL") or "").strip().rstrip("/")
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_TOKEN")

    if not base:
        return "Error: JIRA_URL is not configured."
    if not email or not token:
        return "Error: JIRA_EMAIL or JIRA_API_TOKEN is not configured."

    url = f"{base}/rest/api/3/issue/{issue_id.strip()}"

    try:
        response = httpx.get(
            url,
            params={"fields": FIELDS},
            auth=(email, token),
            headers={"Accept": "application/json"},
            timeout=15.0,
        )
    except httpx.RequestError as exc:
        return f"Error: could not reach Jira ({exc})."

    if response.status_code != 200:
        return f"Error: Jira returned {response.status_code} fetching {issue_id}: {response.text[:300]}"

    issue = _normalize_issue(response.json())
    return _format_issue_text(issue)
