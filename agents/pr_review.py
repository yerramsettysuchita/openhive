"""PR Review Agent — Phase 4 (second fully working agent).

Flow per pull_request event:
  1. Extract PR fields from state.
  2. Fetch the diff (httpx, public URL), truncate to 3000 chars (token discipline).
  3. One Claude call (claude-sonnet-4-6, max_tokens=600) -> JSON review.
  4. Parse JSON.
  5. save_verdict to Supabase BEFORE any GitHub write.
  6. Write finding to ChromaDB.
  7. Cross-pollination: check the Security Agent's prior findings for this repo.
  8. Post a human-sounding review comment to the PR.
  9. Update and return state.

GUARD: PRs opened by OpenHive itself (head branch openhive-security-patch-*)
are skipped with NO Claude call, so the Security Agent's auto patch PR does not
trigger a self-review (avoids an extra, unbudgeted model call).

TOKEN DISCIPLINE: exactly ONE Claude call per reviewed PR, capped at 600
output tokens. The comment is composed locally from the structured result.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from anthropic import Anthropic
from github import Github

from backend.persistence import save_verdict
from consensus.protocol import disagreement_note_for
from memory.chroma_store import write_finding, read_cross_agent

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 600
DIFF_LIMIT = 3000

PR_REVIEW_SYSTEM_PROMPT = (
    "You are the PR Review Agent for OpenHive, an AI maintainer assistant. Your "
    "only job is to review GitHub pull request diffs and produce structured "
    "feedback. You must respond with a valid JSON object and nothing else. The "
    "JSON must have exactly six fields. verdict is one of approve, "
    "request_changes, or comment. confidence is a float between 0 and 1. "
    "breaking_changes is a boolean indicating whether the diff contains "
    "breaking changes. test_coverage_concern is a boolean indicating whether "
    "the diff adds functionality without corresponding tests. "
    "claim_vs_code_drift is a boolean indicating whether the PR description "
    "claims something the diff does not actually implement. review_comment is a "
    "string of two to four sentences written as a senior engineer would write "
    "them, direct and specific about what the diff actually does, not generic "
    "praise or criticism. Do not write anything outside the JSON object."
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


def _build_comment(parsed: dict, cross_note: str) -> str:
    """Compose a warm, specific PR comment. No headers/bullets/bold/em dashes."""
    verdict = parsed.get("verdict", "comment")
    review = (parsed.get("review_comment") or "").strip()

    sentences = [review] if review else []

    if parsed.get("breaking_changes"):
        sentences.append(
            "Worth calling out that this looks like it introduces a breaking "
            "change, so it will need a version note and a heads up for "
            "downstream users."
        )
    if parsed.get("test_coverage_concern"):
        sentences.append(
            "I do not see tests covering the new behavior here, so it would "
            "help to add coverage for the main path before this merges."
        )
    if parsed.get("claim_vs_code_drift"):
        sentences.append(
            "One thing to flag is that the description claims more than the "
            "diff actually implements, so it is worth either trimming the "
            "description or adding the missing piece."
        )
    if cross_note:
        sentences.append(cross_note)

    closers = {
        "approve": "On my read this is close to mergeable once the notes above are settled.",
        "request_changes": "Could you take another pass at the points above and push an update?",
        "comment": "No blocking concerns from me, just the notes above to consider.",
    }
    sentences.append(closers.get(verdict, closers["comment"]))

    comment = "\n\n".join(s for s in sentences if s)
    # Tone rule: no em/en dashes, even if Claude used them in review_comment.
    return comment.replace("—", ", ").replace("–", ", ")


def pr_review_node(state: dict) -> dict:
    payload = state.get("payload", {})
    pr = payload.get("pull_request", {})
    repo_full_name = state.get("repo_full_name") or payload.get("repository", {}).get("full_name")

    number = pr.get("number") or payload.get("number")
    title = pr.get("title")
    body = pr.get("body") or ""
    diff_url = pr.get("diff_url")
    head_ref = (pr.get("head") or {}).get("ref", "")

    # GUARD: never review OpenHive's own security patch PRs (no Claude call).
    if head_ref.startswith("openhive-security-patch"):
        print(f"[OPENHIVE] PR #{number} is an OpenHive patch PR, skipping self-review.")
        return {"agent_called": "pr_review"}

    if not number or not title or not diff_url or not repo_full_name:
        errors = list(state.get("errors", []))
        errors.append("pr_review: missing PR number, title, diff_url, or repository")
        return {"errors": errors}

    print("[OPENHIVE] PR Review Agent called")

    # Step 2: fetch + truncate diff. Try the public diff_url first; fall back
    # to the authenticated GitHub API diff (works for private repos too).
    diff: Optional[str] = None
    try:
        resp = httpx.get(diff_url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            diff = resp.text[:DIFF_LIMIT]
    except Exception:  # noqa: BLE001
        diff = None
    if diff is None:
        try:
            api = f"https://api.github.com/repos/{repo_full_name}/pulls/{number}"
            headers = {
                "Accept": "application/vnd.github.diff",
                "Authorization": f"token {os.getenv('GITHUB_TOKEN_REPO', '')}",
            }
            resp = httpx.get(api, headers=headers, timeout=10.0, follow_redirects=True)
            resp.raise_for_status()
            diff = resp.text[:DIFF_LIMIT]
        except Exception as exc:  # noqa: BLE001
            errors = list(state.get("errors", []))
            errors.append(f"pr_review: failed to fetch diff: {exc}")
            return {"errors": errors}

    # Step 3: one Claude call.
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=PR_REVIEW_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"PR title: {title}\n\nPR description:\n{body}\n\n"
                    f"Diff (truncated to {DIFF_LIMIT} chars):\n{diff}"
                ),
            }
        ],
    )
    print(
        f"[TOKEN USE] pr_review input={message.usage.input_tokens} "
        f"output={message.usage.output_tokens}"
    )
    raw = message.content[0].text
    print(f"[OPENHIVE] Claude review: {raw}")

    # Step 4: parse.
    try:
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        errors = list(state.get("errors", []))
        errors.append(f"pr_review: failed to parse Claude JSON: {exc}")
        return {"errors": errors}

    verdict = parsed.get("verdict", "comment")
    finding_id = f"pr-review-{number}"

    # Step 5: persist verdict BEFORE any GitHub write.
    saved = save_verdict(
        repo_full_name,
        "pull_request",
        "pr_review",
        finding_id,
        parsed,
        classification=verdict,
        confidence=parsed.get("confidence"),
        github_action_taken="posting_review_comment",
    )
    if not saved:
        print("[PERSISTENCE] pr_review verdict not saved, continuing anyway.")

    # Step 6: write finding to ChromaDB.
    metadata = {
        "agent": "pr_review",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": repo_full_name,
        "pr_number": str(number),
        "verdict": verdict,
        "breaking_changes": str(parsed.get("breaking_changes")),
        "test_coverage_concern": str(parsed.get("test_coverage_concern")),
        "claim_vs_code_drift": str(parsed.get("claim_vs_code_drift")),
    }
    write_finding("pr_review", finding_id, raw, metadata)
    print(f"[OPENHIVE] Memory written: {finding_id}")

    # Step 7: cross-pollination with the Security Agent.
    cross_note = ""
    try:
        sec = read_cross_agent(["security"], title, limit=2)
        if sec:
            cross_note = (
                "Heads up, the Security Agent previously flagged a related "
                "concern in this repository, so it is worth a look in that context."
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[OPENHIVE] cross-agent read failed (non-fatal): {exc}")

    # Step 8: post the human comment.
    errors = list(state.get("errors", []))
    try:
        comment = _build_comment(parsed, cross_note)
        comment += disagreement_note_for("pr_review", repo_full_name, verdict, parsed.get("confidence"))
        repo = _github().get_repo(repo_full_name)
        gh_pr = repo.get_pull(number)
        gh_pr.create_issue_comment(comment)
        print(f"[OPENHIVE] GitHub review comment posted to PR #{number}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pr_review: failed to post comment: {exc}")
        print(f"[OPENHIVE] ERROR posting PR comment: {exc}")

    # Step 9: update state.
    finding = {
        "id": finding_id,
        "text": raw,
        "metadata": metadata,
        "verdict": verdict,
        "confidence": parsed.get("confidence"),
    }
    return {"findings": [finding], "agent_called": "pr_review", "errors": errors}
