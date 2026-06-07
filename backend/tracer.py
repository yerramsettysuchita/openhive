"""Observability tracing wrapper — GitHub Models (Microsoft stack).

Every Claude call routed through OpenHive is wrapped here. We use GitHub
Models (OpenAI-compatible endpoint, authenticated with a GitHub PAT) to emit
an observability note for each agent decision, satisfying the Microsoft-stack
requirement. The trace path is best-effort and fully wrapped in try/except so
it can never block or break the request path (graceful-degradation NFR).
"""

import os
from datetime import datetime, timezone
from typing import Optional

from openai import OpenAI

# Cheap, fast model on GitHub Models for one-line observability summaries.
TRACE_MODEL = "openai/gpt-4o-mini"

_tracer_client: Optional[OpenAI] = None


def get_tracer() -> OpenAI:
    """Lazily build the GitHub Models client. Raises if the PAT is absent."""
    global _tracer_client
    if _tracer_client is None:
        token = os.getenv("GITHUB_TOKEN")
        endpoint = os.getenv(
            "GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference"
        )
        if not token:
            raise ValueError("GITHUB_TOKEN not set")
        _tracer_client = OpenAI(base_url=endpoint, api_key=token)
    return _tracer_client


def trace_event(event_type: str, payload: dict, result: str) -> None:
    """Emit one observability trace line for a Claude call, via GitHub Models.

    Best-effort: if GitHub Models is unreachable we still log the trace line
    with a clear marker, never raising into the request path.
    """
    ts = datetime.now(timezone.utc).isoformat()
    repo = payload.get("repository", {}).get("full_name", "unknown")

    note = ""
    try:
        client = get_tracer()
        resp = client.chat.completions.create(
            model=TRACE_MODEL,
            max_tokens=40,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "In 12 words or fewer, summarize this agent decision "
                        f"for an observability log: {result}"
                    ),
                }
            ],
        )
        note = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 — trace must never break the request
        note = f"(trace model unavailable: {type(exc).__name__})"

    print(
        f"[GH MODELS TRACE] ts={ts} event={event_type} repo={repo} "
        f"claude_preview={result[:60]!r} observability_note={note!r}"
    )
