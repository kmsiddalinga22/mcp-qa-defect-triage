"""
Defect triage tool.

Classifies a reported issue's severity and suggests whether it is a
genuine defect or more likely a change request, based on keyword rules.
This mirrors the manual triage process used when clients report
production issues: analyze impact, assign severity, and route
appropriately before it reaches the dev team.
"""

import re
from pathlib import Path

from .jira_client import fetch_jira_issue
from .llm_client import call_llm

TRIAGE_AI_PROMPT_PATH = Path(__file__).parent / "prompts" / "triage_defect_ai.md"


def _run_triage_ai(entries: list[str]) -> str:
    """Fill the shared triage prompt template with one or more defects and call the LLM."""
    combined = "\n\n".join(entries)
    template = TRIAGE_AI_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.replace("{issues}", combined)
    return call_llm(prompt)


SEVERITY_RULES = [
    ("Critical", [r"\bcrash\b", r"\bdata loss\b", r"\boutage\b", r"\bsecurity\b", r"\bdown\b", r"\bcannot log in\b"]),
    ("High", [r"\bblocked\b", r"\bcannot complete\b", r"\bpayment fail", r"\bincorrect data\b", r"\bwrong result\b"]),
    ("Medium", [r"\bslow\b", r"\bui\b", r"\bcosmetic\b", r"\bminor\b", r"\bworkaround\b"]),
    ("Low", [r"\btypo\b", r"\blabel\b", r"\bspacing\b", r"\bcolou?r\b"]),
]

CHANGE_REQUEST_HINTS = [
    r"\bcould we add\b", r"\bwould like\b", r"\bnew feature\b", r"\benhancement\b",
    r"\bnice to have\b", r"\bcan you add\b", r"\bsuggest\b", r"\brequest to change\b",
]

DEFECT_HINTS = [
    r"\bexpected\b.*\bbut\b", r"\bshould\b.*\bbut\b", r"\bnot working\b",
    r"\bfails?\b", r"\berror\b", r"\bbroken\b", r"\bincorrect\b",
]


def _classify_severity(text: str) -> str:
    for severity, patterns in SEVERITY_RULES:
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            return severity
    return "Medium"  # sensible default when no keyword matches


def _classify_type(text: str) -> str:
    is_change_request = any(re.search(p, text, re.IGNORECASE) for p in CHANGE_REQUEST_HINTS)
    is_defect = any(re.search(p, text, re.IGNORECASE) for p in DEFECT_HINTS)

    if is_change_request and not is_defect:
        return "Change Request"
    return "Defect"


def triage_defect(description: str = "", logs: str = "", jira_id: str = "") -> str:
    """
    Triage a reported issue: classify severity and defect-vs-change-request,
    and give a one-line recommended routing action.

    Args:
        description: The issue description as reported by the client/user.
            Optional if jira_id is given instead.
        logs: Optional error log or stack trace snippet for extra context.
        jira_id: Optional Jira issue key (e.g. "QA-123"). When given, the
            issue is fetched from Jira and used as the description
            automatically — description/logs are still appended if provided.

    Returns:
        A formatted triage summary: severity, classification, and
        recommended next step.
    """
    source_text = description

    if jira_id and jira_id.strip():
        fetched = fetch_jira_issue(jira_id)
        if fetched.startswith("Error:"):
            return fetched
        source_text = f"{fetched}\n{description}".strip()

    if not source_text or not source_text.strip():
        return "Error: description or jira_id must be provided."

    combined_text = f"{source_text} {logs}".strip()

    severity = _classify_severity(combined_text)
    issue_type = _classify_type(combined_text)

    if issue_type == "Change Request":
        recommendation = "Route to product backlog for prioritization — not a production defect."
    elif severity == "Critical":
        recommendation = "Escalate immediately to dev team; treat as production-blocking."
    elif severity == "High":
        recommendation = "Route to dev team for next release; verify no workaround exists."
    else:
        recommendation = "Log in defect tracker for scheduled fix; low urgency."

    lines = []
    if jira_id and jira_id.strip():
        lines.append(f"Source: Jira {jira_id.strip()}")
    lines += [
        f"Classification: {issue_type}",
        f"Severity: {severity}",
        f"Recommended Action: {recommendation}",
    ]
    return "\n".join(lines)


def triage_defect_prompt(issue: str = "", jira_id: str = "") -> str:
    """
    Build a prompt asking an LLM to perform a full structured triage of a
    Jira issue: severity, priority, impact areas, root-cause hypothesis,
    and justification.

    Unlike `triage_defect` (fast, deterministic, keyword-based), this hands
    the reasoning to the calling model for deeper, context-aware judgment.

    Args:
        issue: The Jira issue text (title, description, comments, etc.) to
            triage. Optional if jira_id is given instead.
        jira_id: Optional Jira issue key (e.g. "QA-123"). When given, the
            issue is fetched from Jira and used in place of `issue`.

    Returns:
        The filled-in triage prompt, ready to send to an LLM.
    """
    if jira_id and jira_id.strip():
        fetched = fetch_jira_issue(jira_id)
        if fetched.startswith("Error:"):
            return fetched
        issue = fetched

    if not issue or not issue.strip():
        return "Error: issue or jira_id must be provided."

    return f"""You are a senior bug triage engineer. Analyze the Jira issue below and produce a structured triage.

JIRA ISSUE:
{issue}

Assess and decide ALL of the following:
1. SEVERITY — technical impact of the defect. One of: Blocker, Critical, Major, Minor, Trivial.
2. PRIORITY — business urgency to fix. One of: P0, P1, P2, P3, P4.
3. IMPACT_AREAS — list the modules, user journeys, or systems affected.
4. ROOT_CAUSE_ANALYSIS — your best hypothesis of the underlying cause based on the description. If evidence is insufficient, state what is unknown and what data is needed.
5. JUSTIFICATION — one or two sentences explaining the severity/priority decision.

Be decisive. Base every conclusion only on the issue content. Do not invent stack traces or logs."""


def triage_defect_ai(
    issue: str = "",
    jira_id: str = "",
    issues: list[str] | None = None,
    jira_ids: list[str] | None = None,
) -> str:
    """
    Perform a full structured triage using the configured LLM (see
    llm_client.py / LLM_MODEL in .env), returning the actual computed
    analysis rather than a prompt template. Handles one issue or many in a
    single call: pass `issue`/`jira_id` for a single defect, or
    `issues`/`jira_ids` (lists) for several — any combination is merged
    into one batch. With 2+ defects, the LLM also clusters likely
    duplicates; with 1, that section just reads "None".

    Args:
        issue: A single issue's raw text (title, description, logs, etc.).
        jira_id: A single Jira issue key (e.g. "QA-123") to fetch and
            triage.
        issues: Raw text for multiple defects, one string per defect.
        jira_ids: Multiple Jira issue keys to fetch and include.

    Returns:
        The LLM's structured triage: suggested duplicates (if any),
        severity/priority/routing per defect, root-cause hypotheses, and a
        needs-info list, ending with a human review gate.
    """
    entries = []

    if jira_id and jira_id.strip():
        fetched = fetch_jira_issue(jira_id)
        if fetched.startswith("Error:"):
            return fetched
        entries.append(f"### Defect {jira_id.strip()}\n{fetched}")

    if issue and issue.strip():
        entries.append(f"### Defect\n{issue.strip()}")

    for jid in jira_ids or []:
        fetched = fetch_jira_issue(jid)
        if fetched.startswith("Error:"):
            return f"Error fetching {jid}: {fetched}"
        entries.append(f"### Defect {jid.strip()}\n{fetched}")

    for i, text in enumerate(issues or [], start=1):
        if text and text.strip():
            entries.append(f"### Defect #{i}\n{text.strip()}")

    if not entries:
        return "Error: provide at least one of issue, jira_id, issues, or jira_ids."

    return _run_triage_ai(entries)
