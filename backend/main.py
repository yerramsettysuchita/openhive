"""OpenHive FastAPI entrypoint.

Loads environment, mounts the webhook router, exposes the health probe, the
daily-digest trigger, and three read-only endpoints the frontend dashboard
calls (verdicts, health score, stats). The read endpoints make no Claude calls.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402  (import after load_dotenv by design)
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.webhook_router import router  # noqa: E402
from backend.persistence import (  # noqa: E402
    get_verdicts_for_repo,
    get_recent_verdicts,
)

app = FastAPI(title="OpenHive", version="1.0.0")

# Allow the Vercel dashboard (and local dev) to call the read endpoints.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://openhive-omega.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "OpenHive is alive", "env": os.getenv("APP_ENV", "local")}


@app.post("/digest")
async def trigger_digest(repo: str):
    """Generate and post the Daily Digest for a repo. Called by the GitHub
    Action cron and used to demo the digest."""
    from backend.digest import run_digest

    url = await run_digest(repo)
    return {"status": "digest posted", "url": url}


# --- Read-only dashboard endpoints (no Claude calls, no side effects) ---

@app.get("/verdicts")
def verdicts(repo: str | None = None, limit: int = 20):
    """Recent agent verdicts, optionally scoped to one repo."""
    if repo:
        return get_verdicts_for_repo(repo, limit=limit)
    return get_recent_verdicts(limit=limit, hours_back=24 * 365)


@app.get("/health/score")
def health_score(repo: str):
    """Most recent Health Agent score/label for a repo."""
    rows = get_verdicts_for_repo(repo, agent_name="health", limit=1)
    if not rows:
        return {"score": 0, "label": "unknown"}
    raw = rows[0].get("raw_response") or {}
    return {
        "score": raw.get("health_score", 0),
        "label": raw.get("health_label", "unknown"),
    }


@app.get("/stats")
def stats():
    """Aggregate verdict counts for the live activity feed."""
    rows = get_recent_verdicts(limit=500, hours_back=24 * 365)
    per_agent: dict[str, int] = {}
    for r in rows:
        a = r.get("agent_name", "unknown")
        per_agent[a] = per_agent.get(a, 0) + 1
    most_recent = rows[0].get("created_at") if rows else None
    return {
        "total_verdicts": len(rows),
        "per_agent": per_agent,
        "most_recent": most_recent,
    }


@app.get("/swarm/status")
def swarm_status(repo: str):
    """Most recent verdict per agent for a repo, powering the live swarm strip."""
    rows = get_verdicts_for_repo(repo, limit=100)
    status = {}
    for agent in ["triage", "pr_review", "security", "docs", "health"]:
        av = [v for v in rows if v.get("agent_name") == agent]
        if av:
            latest = max(av, key=lambda x: x.get("created_at", ""))
            status[agent] = {
                "last_seen": latest.get("created_at"),
                "classification": latest.get("classification", "unknown"),
                "active": True,
            }
        else:
            status[agent] = {"last_seen": None, "classification": None, "active": False}
    return status


@app.get("/metrics")
def metrics():
    """Live operational metrics: webhook volume, Claude usage and cost, per-agent
    latency, disagreements surfaced, and patch PRs opened."""
    from backend.metrics import get_metrics

    return get_metrics()
