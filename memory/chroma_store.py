"""Shared memory layer — ChromaDB (Phase 2).

The architectural core of OpenHive's shared intelligence. Every agent gets its
own namespaced collection (``openhive_<agent>``) so no agent's write can
corrupt another's read. Findings cross-pollinate across the swarm through
``read_cross_agent``.

TOKEN DISCIPLINE: this module never calls Claude. It performs only local
ChromaDB writes/reads and (local, no-API-cost) embedding. Claude is invoked
solely by agents when a real GitHub webhook event fires in production.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

# The five agents, each with an isolated collection. A name outside this set is
# rejected so no caller can invent or reach across namespaces.
ALLOWED_AGENTS = ("triage", "pr_review", "security", "docs", "health")

# Every finding's metadata must carry at least these three keys.
REQUIRED_META = ("agent", "timestamp", "repository")

# Persist to <project-root>/chroma_db (already in .gitignore).
_CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_db"

# Single module-level client, initialized once. Telemetry disabled — no
# outbound calls beyond local persistence.
_client = chromadb.PersistentClient(
    path=str(_CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)


def _validate_agent(agent_name: str) -> None:
    if agent_name not in ALLOWED_AGENTS:
        raise ValueError(
            f"Unknown agent '{agent_name}'. Must be one of {ALLOWED_AGENTS}."
        )


def get_collection(agent_name: str):
    """Return the namespaced ChromaDB collection for one agent.

    Collection name is always ``openhive_<agent_name>``. There is no path
    through this function to another agent's collection.
    """
    _validate_agent(agent_name)
    return _client.get_or_create_collection(name=f"openhive_{agent_name}")


def write_finding(
    agent_name: str,
    finding_id: str,
    finding_text: str,
    metadata: dict,
) -> None:
    """Write one finding to an agent's collection.

    ``metadata`` must include 'agent', 'timestamp' (UTC ISO string) and
    'repository'. If any is missing, raises ValueError before writing anything.
    """
    _validate_agent(agent_name)

    missing = [k for k in REQUIRED_META if not metadata.get(k)]
    if missing:
        raise ValueError(
            f"metadata missing required key(s): {missing}. "
            f"Required: {REQUIRED_META}"
        )

    collection = get_collection(agent_name)
    collection.upsert(
        ids=[finding_id],
        documents=[finding_text],
        metadatas=[metadata],
    )


def read_findings(
    agent_name: str,
    query: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Read findings from one agent's collection.

    With a ``query`` → semantic similarity search, top ``limit`` results.
    Without → the most recent ``limit`` findings by timestamp metadata.
    Returns a list of {"text", "id", "metadata"} dicts.
    """
    _validate_agent(agent_name)
    collection = get_collection(agent_name)

    if query:
        res = collection.query(
            query_texts=[query],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        out: list[dict] = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i in range(len(ids)):
            out.append(
                {
                    "text": docs[i],
                    "id": ids[i],
                    "metadata": metas[i],
                    "distance": dists[i],
                }
            )
        return out

    # No query: fetch all, sort by timestamp desc, take limit.
    res = collection.get(include=["documents", "metadatas"])
    ids = res.get("ids", [])
    docs = res.get("documents", [])
    metas = res.get("metadatas", [])
    rows = [
        {"text": docs[i], "id": ids[i], "metadata": metas[i]}
        for i in range(len(ids))
    ]
    rows.sort(key=lambda r: r["metadata"].get("timestamp", ""), reverse=True)
    return rows[:limit]


def read_cross_agent(
    agent_names: list[str],
    query: str,
    limit: int = 3,
) -> list[dict]:
    """Cross-pollination: query several agents' collections at once.

    Queries each named agent's collection with ``query``, takes the top
    ``limit`` from each, then merges and re-ranks everything by ChromaDB
    distance score (ascending = most relevant first). This is how, e.g., the
    PR Review Agent sees what the Security Agent already found.
    """
    merged: list[dict] = []
    for agent_name in agent_names:
        _validate_agent(agent_name)
        collection = get_collection(agent_name)
        res = collection.query(
            query_texts=[query],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i in range(len(ids)):
            merged.append(
                {
                    "agent": agent_name,
                    "text": docs[i],
                    "id": ids[i],
                    "metadata": metas[i],
                    "distance": dists[i],
                }
            )

    merged.sort(key=lambda r: r["distance"])
    return merged


def clear_repo_findings(repository_full_name: str) -> int:
    """Delete every finding for a repository across all agent collections.

    Used when a repo disconnects from OpenHive. Returns the number of findings
    deleted.
    """
    deleted = 0
    for agent_name in ALLOWED_AGENTS:
        collection = get_collection(agent_name)
        existing = collection.get(where={"repository": repository_full_name})
        n = len(existing.get("ids", []))
        if n:
            collection.delete(where={"repository": repository_full_name})
            deleted += n
    return deleted


# Convenience helper for callers that need a UTC ISO timestamp for metadata.
def utc_now_iso() -> str:
    return datetime.utcnow().isoformat()
