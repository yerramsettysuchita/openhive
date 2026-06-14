"""GitHub webhook receiver.

Phase 3: every event is routed through the LangGraph agent graph
(backend.graph.app). The signature is verified, the event is parsed, and an
initial graph state is invoked. The graph is now the SINGLE entry point for
all agent logic — there is no direct Claude call in this file anymore.
"""

import hashlib
import hmac
import json
import os

from fastapi import APIRouter, HTTPException, Request

from backend.graph import app as agent_graph
from backend.metrics import record_webhook

router = APIRouter()


def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Validate the X-Hub-Signature-256 header against the shared secret."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


@router.post("/webhook")
async def receive_webhook(request: Request):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    record_webhook(event_type)
    payload = json.loads(payload_bytes)
    repo_full_name = payload.get("repository", {}).get("full_name", "unknown")

    print(f"[OPENHIVE] Received event: {event_type}")

    initial_state = {
        "event_type": event_type,
        "payload": payload,
        "repo_full_name": repo_full_name,
        "findings": [],
        "errors": [],
        "agent_called": "",
        "disagreement_note": None,
    }

    final_state = await agent_graph.ainvoke(initial_state)

    if final_state.get("disagreement_note"):
        print(f"[CONSENSUS] Disagreement detected: {final_state.get('disagreement_note')}")

    return {
        "status": "ok",
        "event": event_type,
        "agent_called": final_state.get("agent_called", ""),
        "errors": final_state.get("errors", []),
        "disagreement_note": final_state.get("disagreement_note"),
    }
