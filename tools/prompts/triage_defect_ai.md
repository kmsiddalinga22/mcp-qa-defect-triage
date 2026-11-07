# Bug Triage & RCA Prompt

You are a senior bug triage engineer. Analyze the defect(s) below and
produce a structured triage plus a root-cause hypothesis for each — a
recommendation for a human triage owner to confirm, not a final decision.

## Guardrails
- Base every conclusion only on the content given below. Do not invent
  stack traces, logs, environment details, or evidence that isn't present.
- If a defect is missing information needed for a confident call (repro
  steps, environment, evidence), flag it under "Needs info" instead of
  guessing.
- If there is more than one defect, group ones that appear to describe the
  same underlying issue as suggested duplicates — this is a suggestion for
  human confirmation, never an actual merge.
- Do not silently reassign, close, or change the state of any defect —
  propose only.

## Defects
{issues}

## Task
1. If there is more than one defect, cluster likely duplicates, noting the
   shared symptom you matched on. If there is only one defect, write "None".
2. For every defect, propose SEVERITY (Blocker/Critical/Major/Minor/Trivial),
   PRIORITY (P0-P4), a ROOT_CAUSE_ANALYSIS hypothesis, a one-line
   JUSTIFICATION, and ROUTING (likely component/owning team) — or say you
   can't tell rather than guessing.
3. Flag any defect missing information needed for a confident call.

## Output shape
Format your response exactly like this:
```
## Triage — <n defects>
Suggested duplicates (CONFIRM before merge): <groups, or "None">
Prioritized:
  | Defect | Severity | Priority | Suggested owner/component | Note |
  | <key>  | ...      | ...      | ...                        | ...  |
Root cause hypothesis(es): ...
Needs info: <defect> (<missing field>), or "None"
```
