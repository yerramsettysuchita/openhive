"""Daily Digest generator (Phase 6) — OpenHive's primary user-facing feature.

Pulls the past 24h of agent verdicts from Supabase, has Claude write a single
plain-English morning note, and posts it as a GitHub Discussion (falling back to
a labeled issue). Triggered by the GitHub Action cron or the /digest endpoint.

TOKEN DISCIPLINE: exactly ONE Claude call per digest, capped at 500 tokens.
"""

import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from anthropic import Anthropic

from backend.persistence import get_recent_verdicts, save_verdict
from memory.chroma_store import write_finding

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 500
CRITICAL_CLASSES = {"bug", "high", "critical", "security", "request_changes"}

DIGEST_SYSTEM_PROMPT = (
    "You are the OpenHive Daily Digest writer. Your job is to turn a structured "
    "summary of AI agent findings into a single cohesive daily report for an "
    "open source maintainer. Write in plain conversational English. The "
    "maintainer is a real engineer who is busy and values directness over "
    "formality. The report must have exactly three sections separated by blank "
    "lines. Section one is a single paragraph of two to three sentences giving "
    "the overall picture of the repository in the past 24 hours. Section two is "
    "a list of the most important findings, maximum five, each as a single "
    "sentence starting with the agent name that found it followed by what it "
    "found. Use plain dashes to separate items in this section only. Section "
    "three is a single paragraph of one to two sentences telling the maintainer "
    "the single most important thing they should do today. No markdown headers. "
    "No bold text. No em dashes anywhere in the output. Write as if you are a "
    "thoughtful colleague leaving a morning note."
)

_anthropic_client: Optional[Anthropic] = None


def _client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


def _verdict_summary(v: dict) -> str:
    raw = v.get("raw_response") or {}
    for k in (
        "review_comment", "pr_description", "key_insight", "gap_summary",
        "reasoning", "recommended_action", "disagreement_summary",
    ):
        if isinstance(raw, dict) and raw.get(k):
            return str(raw[k])[:180]
    return v.get("classification") or ""


def gather_digest_data(repo_full_name: str, hours_back: int = 24) -> dict:
    print(f"[DIGEST] Gathering data for {repo_full_name}")
    all_v = get_recent_verdicts(limit=200, hours_back=hours_back)
    verdicts = [v for v in all_v if v.get("repo_full_name") == repo_full_name]
    print(f"[DIGEST] Found {len(verdicts)} findings in past {hours_back} hours")

    findings_by_agent: dict[str, list] = {}
    for v in verdicts:
        findings_by_agent.setdefault(v.get("agent_name", "unknown"), []).append(v)

    critical = [v for v in verdicts if (v.get("classification") or "") in CRITICAL_CLASSES]

    health_score = None
    for v in findings_by_agent.get("health", []):
        raw = v.get("raw_response") or {}
        if isinstance(raw, dict) and raw.get("health_score") is not None:
            health_score = raw.get("health_score")
            break

    return {
        "total_findings": len(verdicts),
        "findings_by_agent": findings_by_agent,
        "critical_findings": critical,
        "health_score": health_score,
        "repo_full_name": repo_full_name,
    }


def generate_digest_post(data: dict) -> str:
    lines = [
        f"Repository: {data['repo_full_name']}",
        f"Total findings in the past 24 hours: {data['total_findings']}",
        f"Most recent health score: {data['health_score']}",
        "",
        "Findings by agent:",
    ]
    for agent, items in data["findings_by_agent"].items():
        lines.append(f"  {agent} ({len(items)}):")
        for v in items[:5]:
            lines.append(f"    - {v.get('classification')}: {_verdict_summary(v)}")
    if data["critical_findings"]:
        lines.append("")
        lines.append("Critical / high-priority findings:")
        for v in data["critical_findings"][:6]:
            lines.append(f"    - {v.get('agent_name')} ({v.get('classification')}): {_verdict_summary(v)}")

    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=DIGEST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    print(
        f"[TOKEN USE] digest input={message.usage.input_tokens} "
        f"output={message.usage.output_tokens}"
    )
    text = message.content[0].text.strip()
    return text.replace("—", ", ").replace("–", ", ").replace(" , ", ", ").replace("  ", " ").strip()


def _post_discussion(repo_full_name: str, title: str, body: str, token: str) -> str:
    owner, name = repo_full_name.split("/", 1)
    headers = {"Authorization": f"bearer {token}"}
    q = {
        "query": "query($o:String!,$n:String!){repository(owner:$o,name:$n){id discussionCategories(first:20){nodes{id name}}}}",
        "variables": {"o": owner, "n": name},
    }
    r = httpx.post("https://api.github.com/graphql", json=q, headers=headers, timeout=10.0)
    r.raise_for_status()
    repo = r.json()["data"]["repository"]
    repo_id = repo["id"]
    cats = repo["discussionCategories"]["nodes"]
    if not cats:
        raise RuntimeError("no discussion categories (discussions disabled)")
    cat = next((c for c in cats if c["name"] in ("General", "Announcements")), cats[0])
    m = {
        "query": "mutation($r:ID!,$c:ID!,$t:String!,$b:String!){createDiscussion(input:{repositoryId:$r,categoryId:$c,title:$t,body:$b}){discussion{url}}}",
        "variables": {"r": repo_id, "c": cat["id"], "t": title, "b": body},
    }
    r2 = httpx.post("https://api.github.com/graphql", json=m, headers=headers, timeout=10.0)
    r2.raise_for_status()
    j = r2.json()
    if j.get("errors"):
        raise RuntimeError(str(j["errors"]))
    return j["data"]["createDiscussion"]["discussion"]["url"]


def post_digest_to_github(repo_full_name: str, digest_text: str) -> str:
    from github import Github  # local import keeps module import light

    today = datetime.now(timezone.utc).strftime("%B %d %Y")
    title = f"OpenHive Daily Digest ({today})"
    token = os.getenv("GITHUB_TOKEN_REPO", "")

    print("[DIGEST] Posting to GitHub")
    try:
        url = _post_discussion(repo_full_name, title, digest_text, token)
        print(f"[DIGEST] Posted discussion at {url}")
        return url
    except Exception as exc:  # noqa: BLE001
        print(f"[DIGEST] Discussions unavailable ({exc}); falling back to an issue.")

    g = Github(token)
    repo = g.get_repo(repo_full_name)
    try:
        repo.create_label("openhive-digest", "5319E7")
    except Exception:  # noqa: BLE001
        pass
    issue = repo.create_issue(title=title, body=digest_text, labels=["openhive-digest"])
    print(f"[DIGEST] Posted issue at {issue.html_url}")
    return issue.html_url


async def run_digest(repo_full_name: str) -> str:
    """Full digest flow: gather -> generate -> post -> persist."""
    data = gather_digest_data(repo_full_name)
    digest_text = generate_digest_post(data)
    url = post_digest_to_github(repo_full_name, digest_text)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    finding_id = f"digest-{today}"
    metadata = {
        "agent": "digest",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": repo_full_name,
        "url": url,
    }
    write_finding("health", finding_id, digest_text, metadata)
    save_verdict(
        repo_full_name, "schedule", "digest", finding_id,
        {"digest": digest_text, "url": url},
        github_action_taken="daily_digest", github_action_url=url,
    )
    return url
