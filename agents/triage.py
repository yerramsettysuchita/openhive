"""Triage Agent — Phase 3 (first fully working agent).

Flow per issue event:
  1. Extract issue title, body, number, repo from state.
  2. One Claude call (claude-sonnet-4-6, max_tokens=400) -> JSON classification.
  3. Parse the JSON.
  4. Write the finding to ChromaDB (namespaced triage collection).
  5. Post a human-sounding comment back to the GitHub issue.
  6. Update and return state.

TOKEN DISCIPLINE: exactly ONE Claude call per issue event, capped at 400
output tokens. The contributor-facing comment is composed locally from the
structured result — it does NOT cost a second model call. Claude is invoked
only when a real GitHub webhook event triggers this agent in production.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from anthropic import Anthropic
from github import Github

from backend.metrics import record_claude_call
from backend.persistence import save_verdict, verdict_exists
from consensus.protocol import disagreement_note_for
from memory.chroma_store import write_finding

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 400

TRIAGE_SYSTEM_PROMPT = (
    "You are the Triage Agent for OpenHive, an AI maintainer assistant. Your "
    "only job is to classify GitHub issues. You must respond with a valid JSON "
    "object and nothing else. The JSON must have exactly four fields. "
    "classification is one of bug, feature, duplicate, or invalid. confidence "
    "is a float between 0 and 1. clarifying_questions is a list of strings "
    "containing zero to three questions a senior engineer would ask before "
    "touching this issue. reasoning is one sentence explaining your "
    "classification. Do not write anything outside the JSON object."
)

_anthropic_client: Optional[Anthropic] = None
_github_client: Optional[Github] = None


def _client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


def _github() -> Github:
    global _github_client
    if _github_client is None:
        token = os.getenv("GITHUB_TOKEN_REPO")
        if not token:
            raise ValueError("GITHUB_TOKEN_REPO not set")
        _github_client = Github(token)
    return _github_client


def _parse_json(raw: str) -> dict:
    """Parse Claude's JSON, tolerating accidental code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _build_comment(classification: str, questions: list[str]) -> str:
    """Compose a warm, human comment. No markdown headers, bold, bullets, or
    em dashes — just plain sentences a thoughtful engineer would write."""
    openers = {
        "bug": (
            "Thanks for flagging this. It does look like a real bug to me, and "
            "I want to get it reproduced so we can fix it properly."
        ),
        "feature": (
            "Appreciate the suggestion. This reads as a feature request, and "
            "it is a reasonable one to put on the table."
        ),
        "duplicate": (
            "Thanks for taking the time to write this up. I think it overlaps "
            "with something we already have open, so I want to keep the "
            "discussion in one place."
        ),
        "invalid": (
            "Thanks for reaching out. From what I can see this probably is not "
            "a code issue on our side, but I want to be sure I am not missing "
            "anything."
        ),
    }
    closers = {
        "bug": "Once I can reproduce it, I will start digging into the cause.",
        "feature": "I will raise this with the maintainers to weigh against what is already planned.",
        "duplicate": "I will link the related issue so the two stay connected.",
        "invalid": "If any of the above changes the picture, just reply here and I will take another look.",
    }

    opener = openers.get(classification, openers["bug"])
    closer = closers.get(classification, "I will pick this up from here and follow up shortly.")

    parts = [opener]
    if questions:
        lead = "A few things would help me move this forward:"
        parts.append(lead + "\n" + "\n".join(q.strip() for q in questions if q.strip()))
    parts.append(closer)
    comment = "\n\n".join(parts)
    # Tone rule: no em/en dashes, even if Claude produced them in questions.
    return comment.replace("—", ", ").replace("–", ", ")


def triage_node(state: dict) -> dict:
    payload = state.get("payload", {})
    issue = payload.get("issue", {})
    repo_full_name = state.get("repo_full_name") or payload.get("repository", {}).get("full_name")

    title = issue.get("title")
    body = issue.get("body") or ""
    number = issue.get("number")

    # Step 1: required-field guard. (body may legitimately be empty.)
    if not title or number is None or not repo_full_name:
        errors = list(state.get("errors", []))
        errors.append("triage: missing issue title, number, or repository")
        return {"errors": errors}

    # Skip OpenHive's own generated issues (e.g., Health reports) so the swarm
    # does not triage its own output.
    label_names = {l.get("name") for l in issue.get("labels", []) if isinstance(l, dict)}
    if title.startswith("OpenHive") or any(str(n).startswith("openhive-") for n in label_names):
        print(f"[OPENHIVE] Triage Agent: issue #{number} is OpenHive-generated, skipping.")
        return {"agent_called": "triage"}

    # Idempotency guard: skip if we already have a verdict for this issue.
    finding_id = f"triage-{number}"
    if verdict_exists(finding_id):
        print(f"[OPENHIVE] Triage Agent: {finding_id} already processed, skipping.")
        return {"agent_called": "triage"}

    print("[OPENHIVE] Triage Agent called")

    # Step 2: one Claude call, strict token budget.
    _t0 = time.perf_counter()
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=TRIAGE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Issue title: {title}\n\nIssue body:\n{body}",
            }
        ],
    )
    record_claude_call("triage", message.usage.input_tokens, message.usage.output_tokens, (time.perf_counter() - _t0) * 1000)
    print(
        f"[TOKEN USE] triage input={message.usage.input_tokens} "
        f"output={message.usage.output_tokens}"
    )
    raw = message.content[0].text
    print(f"[OPENHIVE] Claude classification: {raw}")

    # Step 3: parse.
    try:
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        errors = list(state.get("errors", []))
        errors.append(f"triage: failed to parse Claude JSON: {exc}")
        return {"errors": errors}

    classification = parsed.get("classification", "invalid")
    questions = parsed.get("clarifying_questions", []) or []

    # Persist verdict BEFORE any GitHub write (auditability NFR).
    save_verdict(
        repo_full_name, "issues", "triage", finding_id, parsed,
        classification=classification, confidence=parsed.get("confidence"),
        github_action_taken="issue_comment",
    )

    # Write finding to ChromaDB.
    metadata = {
        "agent": "triage",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": repo_full_name,
        "issue_number": str(number),
        "classification": classification,
    }
    write_finding("triage", finding_id, raw, metadata)
    print(f"[OPENHIVE] Memory written: {finding_id}")

    # Step 5: post the human-sounding comment.
    errors = list(state.get("errors", []))
    try:
        comment = _build_comment(classification, questions)
        comment += disagreement_note_for("triage", repo_full_name, classification, parsed.get("confidence"))
        comment = comment.replace(" , ", ", ").replace("  ", " ").strip()
        repo = _github().get_repo(repo_full_name)
        gh_issue = repo.get_issue(number=number)
        gh_issue.create_comment(comment)
        print(f"[OPENHIVE] GitHub comment posted to issue #{number}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"triage: failed to post GitHub comment: {exc}")
        print(f"[OPENHIVE] ERROR posting comment: {exc}")

    # Step 6: update state.
    finding = {
        "id": finding_id,
        "text": raw,
        "metadata": metadata,
        "classification": classification,
        "confidence": parsed.get("confidence"),
    }
    return {
        "findings": [finding],
        "agent_called": "triage",
        "errors": errors,
    }
