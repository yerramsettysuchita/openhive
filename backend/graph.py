"""LangGraph agent graph — the router (Phase 3).

This file owns the state schema and the graph topology only. It contains no
agent logic; that lives in the agents/ package. The graph reads the incoming
event and routes it to exactly one agent node.

Routing rules:
  issues          -> triage
  pull_request    -> pr_review
  push (dep file) -> security
  push (.py/.js/.ts/.md) -> docs
  schedule        -> health
  anything else   -> noop
"""

import os
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from agents.triage import triage_node
from agents.pr_review import pr_review_node
from agents.security import security_node
from agents.docs import docs_node
from agents.health import health_node
from consensus.protocol import (
    AgentVerdict,
    enrich_with_cross_agent_verdicts,
    evaluate_consensus,
    format_disagreement_comment,
    log_disagreement,
)


class AgentState(TypedDict):
    event_type: str
    payload: dict
    repo_full_name: str
    findings: list[dict]
    errors: list[str]
    agent_called: str
    disagreement_note: Optional[str]


# Dependency manifests that should wake the Security Agent.
DEP_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
    "pom.xml",
    "build.gradle",
}

# Source/doc extensions that should wake the Docs Agent (scoped — NOT every
# push, to avoid runaway webhook loops).
DOCS_EXTS = (".py", ".js", ".ts", ".md")


from backend.gh_files import changed_files as _changed_files


def touches_dependency_files(payload: dict) -> bool:
    """True if any file in any commit is a dependency manifest."""
    files = _changed_files(payload)
    return any(os.path.basename(f) in DEP_FILES for f in files)


def touches_doc_files(payload: dict) -> bool:
    """True if any file in any commit is a source/doc file (.py/.js/.ts/.md)."""
    files = _changed_files(payload)
    return any(f.endswith(DOCS_EXTS) for f in files)


def route_event(state: AgentState) -> str:
    """Entry point: inspect the event and return the target node name."""
    event_type = state.get("event_type", "")

    if event_type == "issues":
        return "triage"
    if event_type == "pull_request":
        return "pr_review"
    if event_type == "schedule":
        return "health"
    if event_type == "push":
        payload = state.get("payload", {})
        if touches_dependency_files(payload):
            return "security"
        if touches_doc_files(payload):
            return "docs"
        return "noop"
    return "noop"


def noop_node(state: AgentState) -> dict:
    """Unhandled events: log and pass through unchanged."""
    print(f"[OPENHIVE] No agent for event '{state.get('event_type')}', noop.")
    return {"agent_called": "noop"}


def consensus_check_node(state: AgentState) -> dict:
    """Evaluate the swarm's findings for disagreement (pure Python, no Claude).

    Builds AgentVerdict objects from state findings, runs evaluate_consensus,
    and if a disagreement is detected logs it to Supabase and surfaces a
    plain-English note for the maintainer.
    """
    findings = state.get("findings", []) or []
    verdicts = []
    for f in findings:
        meta = f.get("metadata", {}) or {}
        agent = meta.get("agent", "")
        classification = (
            f.get("classification")
            or f.get("verdict")
            or f.get("severity")
            or meta.get("classification")
            or meta.get("verdict")
            or meta.get("severity_summary")
        )
        try:
            confidence = float(f.get("confidence") if f.get("confidence") is not None else 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        verdicts.append(
            AgentVerdict(
                agent_name=agent,
                finding_id=f.get("id", ""),
                classification=classification,
                confidence=confidence,
                raw_response=f.get("metadata", {}),
                timestamp=meta.get("timestamp", ""),
            )
        )

    # Bring in the swarm's recent memory of this repo so disagreement can fire
    # on real single-agent events, not just unit tests.
    repo = state.get("repo_full_name", "")
    current_agent = state.get("agent_called", "")
    verdicts = enrich_with_cross_agent_verdicts(current_agent, repo, verdicts)

    print(f"[CONSENSUS] Evaluated {len(verdicts)} verdict(s) across the swarm.")
    if not verdicts:
        return {}

    result = evaluate_consensus(verdicts)
    if result.get("disagreement_detected"):
        log_disagreement(result, repo)
        return {"disagreement_note": format_disagreement_comment(result)}
    print("[CONSENSUS] Swarm in agreement; no disagreement surfaced.")
    return {}


# Build the graph.
_workflow = StateGraph(AgentState)
_workflow.add_node("triage", triage_node)
_workflow.add_node("pr_review", pr_review_node)
_workflow.add_node("security", security_node)
_workflow.add_node("docs", docs_node)
_workflow.add_node("health", health_node)
_workflow.add_node("noop", noop_node)
_workflow.add_node("consensus_check", consensus_check_node)

_workflow.add_conditional_edges(
    START,
    route_event,
    {
        "triage": "triage",
        "pr_review": "pr_review",
        "security": "security",
        "docs": "docs",
        "health": "health",
        "noop": "noop",
    },
)

# Every agent flows through the consensus check before the graph ends.
for _node in ("triage", "pr_review", "security", "docs", "health", "noop"):
    _workflow.add_edge(_node, "consensus_check")
_workflow.add_edge("consensus_check", END)

# Compiled graph — the single entry point used by the webhook router.
app = _workflow.compile()
