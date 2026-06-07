"""Docs Agent — Phase 5 (fourth agent).

Flow per push event:
  1. Default-branch + doc-file guard (scoped trigger; .py/.js/.ts/.md/CHANGELOG).
  2. Fetch up to 3 qualifying files (alphabetical), 500 chars each.
  3. One Claude call (claude-sonnet-4-6, max_tokens=300) -> JSON gap report.
  4. Parse JSON.
  5. save_verdict to Supabase BEFORE any GitHub write.
  6. Write finding to ChromaDB.
  7. If gaps_found, post a human commit comment on the pushed commit.
  8. Update and return state.

GUARD: only pushes to the DEFAULT branch are processed, matching the Phase 1
architecture decision and avoiding comment noise on every feature branch.

TOKEN DISCIPLINE: exactly ONE Claude call per qualifying push, capped at 300.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from anthropic import Anthropic
from github import Github

from backend.persistence import save_verdict
from backend.gh_files import changed_files
from memory.chroma_store import write_finding

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 300
DOC_EXTS = (".py", ".js", ".ts", ".md")
CHANGELOG_NAMES = {"CHANGELOG", "CHANGELOG.md", "CHANGELOG.txt"}
FILE_CHAR_LIMIT = 500

DOCS_SYSTEM_PROMPT = (
    "You are the Docs Agent for OpenHive, an AI maintainer assistant. Your only "
    "job is to review code and documentation files and identify documentation "
    "gaps. You must respond with a valid JSON object and nothing else. The JSON "
    "must have exactly three fields. gaps_found is a boolean. gap_summary is a "
    "single sentence describing the most important documentation gap found, or "
    'the string "No significant documentation gaps found" if gaps_found is '
    "false. suggested_action is one of add_docstrings, update_readme, "
    "update_changelog, or none."
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
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _qualifies(path: str) -> bool:
    return path.endswith(DOC_EXTS) or os.path.basename(path) in CHANGELOG_NAMES


def _changed_doc_files(payload: dict) -> list[str]:
    # Shared three-tier detector (commits -> head_commit -> compare API).
    return sorted(f for f in changed_files(payload) if _qualifies(f))


def docs_node(state: dict) -> dict:
    payload = state.get("payload", {})
    repo_full_name = state.get("repo_full_name") or payload.get("repository", {}).get("full_name")
    default_branch = payload.get("repository", {}).get("default_branch", "main")
    ref = payload.get("ref", "")
    sha = payload.get("after") or (payload.get("head_commit") or {}).get("id", "")

    # Step 1: scoped trigger.
    if ref and ref != f"refs/heads/{default_branch}":
        print(f"[OPENHIVE] Docs Agent: push to {ref} is not the default branch, skipping.")
        return {"agent_called": "docs"}

    doc_files = _changed_doc_files(payload)
    if not doc_files:
        print("[OPENHIVE] Docs Agent: no documentation-relevant files in this push, skipping.")
        return {"agent_called": "docs"}

    print(f"[OPENHIVE] Docs Agent called for files: {doc_files[:3]}")
    repo = _github().get_repo(repo_full_name)

    # Step 2: fetch up to 3 files, 500 chars each.
    blocks = []
    for path in doc_files[:3]:
        try:
            cf = repo.get_contents(path, ref=sha or default_branch)
            content = cf.decoded_content.decode("utf-8", errors="replace")[:FILE_CHAR_LIMIT]
            blocks.append(f"File: {path}\n{content}")
        except Exception as exc:  # noqa: BLE001
            print(f"[OPENHIVE] Docs Agent could not fetch {path}: {exc}")

    if not blocks:
        return {"agent_called": "docs", "errors": list(state.get("errors", [])) + ["docs: no file contents fetched"]}

    # Step 3: one Claude call.
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=DOCS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n\n".join(blocks)}],
    )
    print(
        f"[TOKEN USE] docs input={message.usage.input_tokens} "
        f"output={message.usage.output_tokens}"
    )
    raw = message.content[0].text
    print(f"[OPENHIVE] Claude docs report: {raw}")

    # Step 4: parse.
    try:
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        return {"errors": list(state.get("errors", [])) + [f"docs: parse failed: {exc}"]}

    gaps_found = bool(parsed.get("gaps_found"))
    suggested_action = parsed.get("suggested_action", "none")
    sha8 = (sha or "nosha")[:8]
    finding_id = f"docs-{sha8}"

    # Step 5: persist BEFORE any GitHub write.
    save_verdict(
        repo_full_name, "push", "docs", finding_id, parsed,
        classification=suggested_action, github_action_taken="commit_comment" if gaps_found else "none",
    )

    # Step 6: ChromaDB.
    metadata = {
        "agent": "docs",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": repo_full_name,
        "gaps_found": str(gaps_found),
        "suggested_action": suggested_action,
    }
    write_finding("docs", finding_id, raw, metadata)
    print(f"[OPENHIVE] Memory written: {finding_id}")

    # Step 7: post commit comment if gaps found.
    errors = list(state.get("errors", []))
    if gaps_found and sha:
        try:
            gap = (parsed.get("gap_summary") or "").strip()
            action_phrases = {
                "add_docstrings": "Adding short docstrings to the new functions would make this much easier to follow.",
                "update_readme": "It would help to update the README so it matches what the code now does.",
                "update_changelog": "Worth adding a changelog entry so this change is easy to trace later.",
                "none": "A small documentation note here would help future readers.",
            }
            follow = action_phrases.get(suggested_action, action_phrases["none"])
            body = f"{gap} {follow}".replace("—", ", ").replace("–", ", ").replace(" , ", ", ").replace("  ", " ").strip()
            commit = repo.get_commit(sha)
            commit.create_comment(body)
            print(f"[OPENHIVE] Docs commit comment posted on {sha8}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"docs: failed to post commit comment: {exc}")
            print(f"[OPENHIVE] ERROR posting docs comment: {exc}")

    finding = {"id": finding_id, "text": raw, "metadata": metadata, "classification": suggested_action}
    return {"findings": [finding], "agent_called": "docs", "errors": errors}
