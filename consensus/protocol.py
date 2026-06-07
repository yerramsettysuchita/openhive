"""Transparent Disagreement Protocol — Phase 5.

The philosophical and architectural core of OpenHive. Pure Python, NO Claude
calls. When agents diverge on a repository event, the disagreement is named,
surfaced, and persisted rather than silently averaged away.

NOTE ON confidence_delta: the Phase 5 spec text says "highest minus second
highest" but the spec's own test asserts disagreement on inputs 0.9 / 0.88 /
0.55 "because the delta between the highest and lowest exceeds 0.3". Those two
definitions conflict for 3+ verdicts. We use highest MINUS lowest (the spread
across the swarm), which satisfies the stated test and is the meaningful signal
("do any two agents diverge?"). For two verdicts the two definitions coincide.
"""

import uuid
from dataclasses import dataclass
from typing import Optional

from backend.persistence import save_verdict, get_recent_repo_verdicts


@dataclass
class AgentVerdict:
    agent_name: str
    finding_id: str
    classification: Optional[str]
    confidence: float
    raw_response: dict
    timestamp: str


def _confidence_label(c: float) -> str:
    if c >= 0.8:
        return "very confident"
    if c >= 0.6:
        return "fairly confident"
    if c >= 0.4:
        return "somewhat unsure"
    return "quite unsure"


def enrich_with_cross_agent_verdicts(
    current_agent: str,
    repo_full_name: str,
    verdicts: list[AgentVerdict],
) -> list[AgentVerdict]:
    """Merge the current event's verdicts with recent verdicts from OTHER agents
    on the same repo (from Supabase, past 48h, up to 4). This is what makes the
    disagreement protocol fire on real single-agent events: the swarm's recent
    memory of the repo is brought into every consensus check.

    If Supabase is unavailable, returns the original list unchanged.
    """
    try:
        rows = get_recent_repo_verdicts(
            repo_full_name, hours_back=48, exclude_agent=current_agent, limit=4
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[CONSENSUS] cross-agent enrichment unavailable: {exc}")
        return verdicts

    enriched = list(verdicts)
    for r in rows:
        conf = r.get("confidence")
        if conf is None:
            conf = 0.5
        enriched.append(
            AgentVerdict(
                agent_name=r.get("agent_name", ""),
                finding_id=r.get("finding_id", ""),
                classification=r.get("classification"),
                confidence=float(conf),
                raw_response=r.get("raw_response") or {},
                timestamp=str(r.get("created_at", "")),
            )
        )
    return enriched


def evaluate_consensus(verdicts: list[AgentVerdict]) -> dict:
    """Weighted evaluation across agent verdicts. Pure Python, no model call."""
    agents_involved = [v.agent_name for v in verdicts]

    if not verdicts:
        return {
            "consensus_reached": True,
            "winning_verdict": None,
            "confidence_delta": 0.0,
            "disagreement_detected": False,
            "disagreement_summary": None,
            "agents_involved": [],
            "recommendation": "No verdicts to evaluate.",
        }

    ordered = sorted(verdicts, key=lambda v: v.confidence, reverse=True)
    highest, lowest = ordered[0], ordered[-1]
    winning_verdict = highest.classification

    delta = 0.0 if len(ordered) == 1 else round(highest.confidence - lowest.confidence, 4)
    disagreement = delta > 0.3

    if disagreement:
        summary = (
            f"{highest.agent_name} is {_confidence_label(highest.confidence)} this is "
            f"'{highest.classification}', while {lowest.agent_name} reads it as "
            f"'{lowest.classification}' and is {_confidence_label(lowest.confidence)}."
        )
        recommendation = (
            "The agents disagree meaningfully, so this is worth a quick human "
            "look before any automated action."
        )
    else:
        summary = None
        recommendation = (
            f"The swarm broadly agrees this is '{winning_verdict}', so you can "
            "proceed on that basis."
        )

    return {
        "consensus_reached": not disagreement,
        "winning_verdict": winning_verdict,
        "confidence_delta": delta,
        "disagreement_detected": disagreement,
        "disagreement_summary": summary,
        "agents_involved": agents_involved,
        "recommendation": recommendation,
        # Extra context for format_disagreement_comment (not in the required set).
        "_high": {
            "agent": highest.agent_name,
            "classification": highest.classification,
            "label": _confidence_label(highest.confidence),
        },
        "_low": {
            "agent": lowest.agent_name,
            "classification": lowest.classification,
            "label": _confidence_label(lowest.confidence),
        },
    }


def format_disagreement_comment(result: dict) -> str:
    """A senior-engineer summary of the disagreement. <=4 sentences, no headers,
    bullets, em dashes, percentages, or jargon."""
    if not result.get("disagreement_detected"):
        return ""

    high = result.get("_high", {})
    low = result.get("_low", {})

    s1 = "The agents looked at this together and did not fully agree."
    s2 = (
        f"The {high.get('agent')} is {high.get('label')} that this is "
        f"{high.get('classification')}, while the {low.get('agent')} sees it more "
        f"as {low.get('classification')} and is {low.get('label')}."
    )
    s3 = (
        "Because their reads diverge this far, it is worth a quick human "
        "judgment rather than letting the swarm act on its own."
    )
    s4 = "A little more context on the change would help the agents converge."

    comment = " ".join([s1, s2, s3, s4])
    return comment.replace("—", ", ").replace("–", ", ")


def log_disagreement(disagreement: dict, repo_full_name: str) -> bool:
    """Persist a consensus result to Supabase under agent_name 'consensus'."""
    finding_id = f"consensus-{uuid.uuid4().hex[:8]}"
    classification = "disagreement" if disagreement.get("disagreement_detected") else "agreement"
    return save_verdict(
        repo_full_name,
        "consensus",
        "consensus",
        finding_id,
        disagreement,
        classification=classification,
        confidence=disagreement.get("confidence_delta"),
    )
