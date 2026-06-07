"""Phase 2 verification for the ChromaDB shared memory layer.

Proves write / read / cross-agent / cleanup work end to end using PLAIN
STRINGS ONLY. No Claude calls anywhere — token discipline enforced.

Run:  python memory/test_memory.py
Success condition: the final "All tests passed" line prints with no errors.
"""

import sys
from datetime import datetime, timezone

# Allow running as `python memory/test_memory.py` from the project root.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from memory.chroma_store import (  # noqa: E402
    write_finding,
    read_findings,
    read_cross_agent,
    clear_repo_findings,
)

REPO = "testorg/testrepo"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _meta(agent: str) -> dict:
    return {"agent": agent, "timestamp": _ts(), "repository": REPO}


def main() -> int:
    failures: list[str] = []

    def check(step: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS - {step}")
        else:
            print(f"FAIL - {step}: {detail}")
            failures.append(step)

    # Step 1: write three triage findings.
    try:
        write_finding("triage", "triage-001", "User reports app crashes on startup with a null pointer.", _meta("triage"))
        write_finding("triage", "triage-002", "Feature request: add dark mode toggle to settings page.", _meta("triage"))
        write_finding("triage", "triage-003", "Duplicate of an existing issue about slow database queries.", _meta("triage"))
        check("Step 1: write 3 findings to triage", True)
    except Exception as exc:  # noqa: BLE001
        check("Step 1: write 3 findings to triage", False, repr(exc))

    # Step 2: write two security findings.
    try:
        write_finding("security", "security-001", "CVE-2024-1234 found in the requests dependency, high severity.", _meta("security"))
        write_finding("security", "security-002", "Outdated cryptography package with a known vulnerability.", _meta("security"))
        check("Step 2: write 2 findings to security", True)
    except Exception as exc:  # noqa: BLE001
        check("Step 2: write 2 findings to security", False, repr(exc))

    # Step 3: read triage with no query -> expect 3.
    try:
        triage_rows = read_findings("triage")
        check("Step 3: read triage (no query) returns 3", len(triage_rows) == 3, f"got {len(triage_rows)}")
    except Exception as exc:  # noqa: BLE001
        check("Step 3: read triage (no query) returns 3", False, repr(exc))

    # Step 4: read security with a query -> expect results.
    try:
        sec_rows = read_findings("security", query="vulnerability dependency")
        check("Step 4: read security (query) returns results", len(sec_rows) > 0, f"got {len(sec_rows)}")
    except Exception as exc:  # noqa: BLE001
        check("Step 4: read security (query) returns results", False, repr(exc))

    # Step 5: cross-agent read across triage + security -> expect both present.
    try:
        cross = read_cross_agent(["triage", "security"], "issue with dependency")
        agents_seen = {row["agent"] for row in cross}
        check(
            "Step 5: cross-agent read merges triage + security",
            len(cross) > 0 and {"triage", "security"}.issubset(agents_seen),
            f"got {len(cross)} rows from agents {agents_seen}",
        )
    except Exception as exc:  # noqa: BLE001
        check("Step 5: cross-agent read merges triage + security", False, repr(exc))

    # Step 6: clear repo findings -> expect both collections empty for repo.
    try:
        deleted = clear_repo_findings(REPO)
        triage_after = read_findings("triage")
        sec_after = read_findings("security")
        check(
            "Step 6: clear_repo_findings removes all findings",
            len(triage_after) == 0 and len(sec_after) == 0,
            f"deleted={deleted}, triage_left={len(triage_after)}, security_left={len(sec_after)}",
        )
    except Exception as exc:  # noqa: BLE001
        check("Step 6: clear_repo_findings removes all findings", False, repr(exc))

    print("-" * 60)
    if failures:
        print(f"Phase 2 FAILED. {len(failures)} step(s) failed: {failures}")
        return 1
    print("Phase 2 memory layer verified. All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
