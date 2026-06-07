"""Supabase persistence layer (Phase 4).

The single interface between agents and Supabase. No agent imports supabase
directly — every agent calls these functions only.

Auditability rule (NFR): save_verdict is called BEFORE any GitHub API write in
every agent, so no action is taken that cannot be audited.

Graceful degradation: if SUPABASE_URL / SUPABASE_KEY are missing the client is
None and every function logs once and returns safely. Nothing here ever raises
into an agent — a persistence failure must never crash the swarm.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from supabase import create_client, Client
except Exception:  # pragma: no cover - import guard
    create_client = None
    Client = None

_TABLE = "agent_verdicts"

_client: "Optional[Client]" = None
_warned = False


def _get_client():
    """Lazily build the Supabase client, or None if unconfigured."""
    global _client, _warned
    if _client is not None:
        return _client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key or create_client is None:
        if not _warned:
            print("[PERSISTENCE] Supabase not configured — verdicts will not be saved.")
            _warned = True
        return None
    _client = create_client(url, key)
    return _client


def save_verdict(
    repo_full_name: str,
    event_type: str,
    agent_name: str,
    finding_id: str,
    raw_response: dict,
    *,
    classification: Optional[str] = None,
    confidence: Optional[float] = None,
    github_action_taken: Optional[str] = None,
    github_action_url: Optional[str] = None,
    error_occurred: bool = False,
    error_message: Optional[str] = None,
) -> bool:
    """Insert one verdict row. Returns True on success, False otherwise.

    Never raises — a failed insert is logged and returns False so the agent can
    decide whether to continue.
    """
    client = _get_client()
    if client is None:
        return False

    row = {
        "repo_full_name": repo_full_name,
        "event_type": event_type,
        "agent_name": agent_name,
        "finding_id": finding_id,
        "raw_response": raw_response,
        "classification": classification,
        "confidence": confidence,
        "github_action_taken": github_action_taken,
        "github_action_url": github_action_url,
        "error_occurred": error_occurred,
        "error_message": error_message,
    }
    try:
        client.table(_TABLE).insert(row).execute()
        print(f"[PERSISTENCE] Verdict saved: {finding_id}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[PERSISTENCE] Failed to save verdict {finding_id}: {exc}")
        return False


def get_verdicts_for_repo(
    repo_full_name: str,
    agent_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Verdicts for one repo, newest first. Optional agent filter."""
    client = _get_client()
    if client is None:
        return []
    try:
        q = (
            client.table(_TABLE)
            .select("*")
            .eq("repo_full_name", repo_full_name)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if agent_name:
            q = q.eq("agent_name", agent_name)
        return q.execute().data or []
    except Exception as exc:  # noqa: BLE001
        print(f"[PERSISTENCE] get_verdicts_for_repo failed: {exc}")
        return []


def get_recent_verdicts(limit: int = 50, hours_back: int = 24) -> list[dict]:
    """All verdicts across repos from the past hours_back hours, newest first."""
    client = _get_client()
    if client is None:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    try:
        return (
            client.table(_TABLE)
            .select("*")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[PERSISTENCE] get_recent_verdicts failed: {exc}")
        return []


def get_recent_repo_verdicts(
    repo_full_name: str,
    hours_back: int = 48,
    exclude_agent: Optional[str] = None,
    limit: int = 4,
) -> list[dict]:
    """Recent verdicts for one repo within a time window, optionally excluding
    one agent. Used by the consensus layer to pull cross-agent signals."""
    client = _get_client()
    if client is None:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    try:
        q = (
            client.table(_TABLE)
            .select("*")
            .eq("repo_full_name", repo_full_name)
            .gte("created_at", cutoff)
        )
        if exclude_agent:
            q = q.neq("agent_name", exclude_agent)
        return q.order("created_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:  # noqa: BLE001
        print(f"[PERSISTENCE] get_recent_repo_verdicts failed: {exc}")
        return []


def verdict_exists(finding_id: str) -> bool:
    """True if a verdict with this finding_id already exists (idempotency)."""
    client = _get_client()
    if client is None:
        return False
    try:
        res = (
            client.table(_TABLE)
            .select("finding_id")
            .eq("finding_id", finding_id)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:  # noqa: BLE001
        print(f"[PERSISTENCE] verdict_exists failed: {exc}")
        return False
