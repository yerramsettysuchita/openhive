"""Health Agent — Phase 5 (fifth agent).

Flow per scheduled event:
  1. Gather repo metrics via PyGitHub (issues, PRs, recent commits/contributors,
     last commit date, stale branches).
  2. One Claude call (claude-sonnet-4-6, max_tokens=400) -> JSON health report.
  3. Parse JSON.
  4. save_verdict to Supabase BEFORE any GitHub write.
  5. Write finding to ChromaDB.
  6. Post a GitHub Discussion (GraphQL); fall back to a labeled issue.
  7. Update and return state.

Runs on a GitHub Actions cron in production (not a backend scheduler).

TOKEN DISCIPLINE: exactly ONE Claude call per scheduled run, capped at 400.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from anthropic import Anthropic
from github import Github

from backend.metrics import record_claude_call
from backend.persistence import save_verdict
from memory.chroma_store import write_finding

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 400

HEALTH_SYSTEM_PROMPT = (
    "You are the Health Agent for OpenHive, an AI maintainer assistant. Your "
    "only job is to assess the health of an open source repository based on "
    "activity metrics and produce a structured health report. You must respond "
    "with a valid JSON object and nothing else. The JSON must have exactly four "
    "fields. health_score is an integer from 0 to 100. health_label is one of "
    "thriving, stable, slowing, or at_risk. key_insight is a single sentence "
    "identifying the most important signal in the metrics, positive or "
    "concerning. recommended_action is a single sentence telling the maintainer "
    "the one most valuable thing they could do right now."
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


def _gather_metrics(repo) -> dict:
    now = datetime.now(timezone.utc)
    since_30 = now - timedelta(days=30)
    since_60 = now - timedelta(days=60)

    open_prs = repo.get_pulls(state="open").totalCount
    open_issues_incl_prs = repo.get_issues(state="open").totalCount
    open_issues = max(open_issues_incl_prs - open_prs, 0)

    commits_30 = repo.get_commits(since=since_30)
    commit_count = commits_30.totalCount
    contributors = set()
    for c in commits_30[:100]:
        if c.author:
            contributors.add(c.author.login)
        elif c.commit and c.commit.author:
            contributors.add(c.commit.author.name)

    try:
        last_commit_date = repo.get_commits()[0].commit.author.date.isoformat()
    except Exception:  # noqa: BLE001
        last_commit_date = "unknown"

    stale = 0
    for b in repo.get_branches():
        if b.name == repo.default_branch:
            continue
        try:
            d = b.commit.commit.author.date
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d < since_60:
                stale += 1
        except Exception:  # noqa: BLE001
            pass

    return {
        "open_issues": open_issues,
        "open_pull_requests": open_prs,
        "commits_last_30_days": commit_count,
        "unique_contributors_last_30_days": len(contributors),
        "most_recent_commit_date": last_commit_date,
        "stale_branches": stale,
    }


def _post_discussion(repo_full_name: str, title: str, body: str, token: str) -> str:
    """Create a GitHub Discussion via GraphQL. Raises on any failure."""
    owner, name = repo_full_name.split("/", 1)
    headers = {"Authorization": f"bearer {token}"}
    q = {
        "query": "query($o:String!,$n:String!){repository(owner:$o,name:$n){id discussionCategories(first:10){nodes{id name}}}}",
        "variables": {"o": owner, "n": name},
    }
    r = httpx.post("https://api.github.com/graphql", json=q, headers=headers, timeout=10.0)
    r.raise_for_status()
    data = r.json()["data"]["repository"]
    repo_id = data["id"]
    cats = data["discussionCategories"]["nodes"]
    if not cats:
        raise RuntimeError("no discussion categories (discussions likely disabled)")
    cat_id = cats[0]["id"]
    m = {
        "query": "mutation($r:ID!,$c:ID!,$t:String!,$b:String!){createDiscussion(input:{repositoryId:$r,categoryId:$c,title:$t,body:$b}){discussion{url}}}",
        "variables": {"r": repo_id, "c": cat_id, "t": title, "b": body},
    }
    r2 = httpx.post("https://api.github.com/graphql", json=m, headers=headers, timeout=10.0)
    r2.raise_for_status()
    j = r2.json()
    if j.get("errors"):
        raise RuntimeError(str(j["errors"]))
    return j["data"]["createDiscussion"]["discussion"]["url"]


def health_node(state: dict) -> dict:
    payload = state.get("payload", {})
    repo_full_name = state.get("repo_full_name") or payload.get("repository", {}).get("full_name")
    if not repo_full_name:
        return {"errors": list(state.get("errors", [])) + ["health: missing repository"]}

    print("[OPENHIVE] Health Agent called")
    repo = _github().get_repo(repo_full_name)

    # Step 1: metrics.
    metrics = _gather_metrics(repo)
    print(f"[OPENHIVE] Health metrics: {metrics}")

    # Step 2: one Claude call.
    metric_text = "\n".join(f"{k}: {v}" for k, v in metrics.items())
    _t0 = time.perf_counter()
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=HEALTH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Repository metrics:\n{metric_text}"}],
    )
    record_claude_call("health", message.usage.input_tokens, message.usage.output_tokens, (time.perf_counter() - _t0) * 1000)
    print(
        f"[TOKEN USE] health input={message.usage.input_tokens} "
        f"output={message.usage.output_tokens}"
    )
    raw = message.content[0].text
    print(f"[OPENHIVE] Claude health report: {raw}")

    # Step 3: parse.
    try:
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        return {"errors": list(state.get("errors", [])) + [f"health: parse failed: {exc}"]}

    score = parsed.get("health_score")
    label = parsed.get("health_label", "unknown")
    key_insight = (parsed.get("key_insight") or "").strip()
    action = (parsed.get("recommended_action") or "").strip()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    finding_id = f"health-{today}"

    # Step 4: persist BEFORE any GitHub write.
    save_verdict(
        repo_full_name, "schedule", "health", finding_id, parsed,
        classification=label, confidence=(score / 100.0 if isinstance(score, (int, float)) else None),
        github_action_taken="discussion_or_issue",
    )

    # Step 5: ChromaDB.
    metadata = {
        "agent": "health",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": repo_full_name,
        "health_score": str(score),
        "health_label": label,
    }
    write_finding("health", finding_id, raw, metadata)
    print(f"[OPENHIVE] Memory written: {finding_id}")

    # Step 6: post Discussion (fallback to labeled issue).
    title = f"OpenHive Health Report ({today})"
    p1 = f"This repository is currently scoring {score} out of 100, which puts it in the {label} range."
    p2 = f"{key_insight} It is the signal most worth keeping an eye on as the project moves forward."
    p3 = f"{action} You are carrying a lot here, and steady attention to this one thing will go a long way."
    body = "\n\n".join([p1, p2, p3]).replace("—", ", ").replace("–", ", ").replace(" , ", ", ").replace("  ", " ").strip()

    errors = list(state.get("errors", []))
    posted = False
    try:
        url = _post_discussion(repo_full_name, title, body, os.getenv("GITHUB_TOKEN_REPO", ""))
        print(f"[OPENHIVE] Health Discussion posted: {url}")
        posted = True
    except Exception as exc:  # noqa: BLE001
        print(f"[OPENHIVE] Discussions unavailable ({exc}); falling back to an issue.")

    if not posted:
        try:
            try:
                repo.create_label("openhive-health", "0E8A16")
            except Exception:  # noqa: BLE001
                pass  # label probably already exists
            issue = repo.create_issue(title=title, body=body, labels=["openhive-health"])
            print(f"[OPENHIVE] Health issue opened: {issue.html_url}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"health: failed to post discussion or issue: {exc}")
            print(f"[OPENHIVE] ERROR posting health output: {exc}")

    finding = {"id": finding_id, "text": raw, "metadata": metadata, "classification": label}
    return {"findings": [finding], "agent_called": "health", "errors": errors}
