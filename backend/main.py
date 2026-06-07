"""OpenHive FastAPI entrypoint (Phase 1: the nervous system).

Loads environment, mounts the webhook router, and exposes a health probe.
No agents, no LangGraph yet — just a server that receives a GitHub event,
makes one traced Claude call, and returns 200.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402  (import after load_dotenv by design)

from backend.webhook_router import router  # noqa: E402

app = FastAPI(title="OpenHive", version="0.1.0")
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
