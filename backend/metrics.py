"""In-memory observability metrics for OpenHive.

Module-level counters that persist for the lifetime of the server process and
are exposed at GET /metrics. This is deliberately dependency-free: no Prometheus
client, no external store, just honest counters that show webhook volume, Claude
usage and cost, per-agent latency, disagreements surfaced, and patch PRs opened.
"""

import time
from datetime import datetime, timezone
from threading import Lock

_lock = Lock()
_start_perf = time.time()
_server_start_time = datetime.now(timezone.utc).isoformat()

# Claude Sonnet pricing, USD per million tokens.
_INPUT_RATE = 3.0
_OUTPUT_RATE = 15.0

_state = {
    "total_webhooks_received": 0,
    "webhooks_by_event_type": {},
    "total_claude_calls": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "latency_sum_by_agent": {},
    "calls_by_agent": {},
    "total_disagreements_surfaced": 0,
    "total_patch_prs_opened": 0,
}


def record_webhook(event_type: str) -> None:
    with _lock:
        _state["total_webhooks_received"] += 1
        et = _state["webhooks_by_event_type"]
        et[event_type] = et.get(event_type, 0) + 1


def record_claude_call(agent_name: str, input_tokens: int, output_tokens: int, latency_ms: float) -> None:
    with _lock:
        _state["total_claude_calls"] += 1
        _state["total_input_tokens"] += int(input_tokens or 0)
        _state["total_output_tokens"] += int(output_tokens or 0)
        _state["latency_sum_by_agent"][agent_name] = _state["latency_sum_by_agent"].get(agent_name, 0.0) + float(latency_ms)
        _state["calls_by_agent"][agent_name] = _state["calls_by_agent"].get(agent_name, 0) + 1


def record_disagreement() -> None:
    with _lock:
        _state["total_disagreements_surfaced"] += 1


def record_patch_pr() -> None:
    with _lock:
        _state["total_patch_prs_opened"] += 1


def get_metrics() -> dict:
    with _lock:
        avg_latency = {
            agent: round(_state["latency_sum_by_agent"][agent] / _state["calls_by_agent"][agent], 1)
            for agent in _state["calls_by_agent"]
        }
        cost = (
            _state["total_input_tokens"] / 1_000_000 * _INPUT_RATE
            + _state["total_output_tokens"] / 1_000_000 * _OUTPUT_RATE
        )
        return {
            "server_start_time": _server_start_time,
            "uptime_seconds": round(time.time() - _start_perf, 1),
            "total_webhooks_received": _state["total_webhooks_received"],
            "webhooks_by_event_type": dict(_state["webhooks_by_event_type"]),
            "total_claude_calls": _state["total_claude_calls"],
            "total_input_tokens": _state["total_input_tokens"],
            "total_output_tokens": _state["total_output_tokens"],
            "total_cost_usd": round(cost, 6),
            "average_latency_ms_by_agent": avg_latency,
            "total_disagreements_surfaced": _state["total_disagreements_surfaced"],
            "total_patch_prs_opened": _state["total_patch_prs_opened"],
        }
