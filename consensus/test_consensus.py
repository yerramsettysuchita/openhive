"""Phase 5 verification for the Transparent Disagreement Protocol.

No Claude calls, no GitHub API calls. Pure logic test.

Run:  python consensus/test_consensus.py
Success: prints "Phase 5 consensus layer verified. All tests passed."
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from consensus.protocol import (  # noqa: E402
    AgentVerdict,
    evaluate_consensus,
    format_disagreement_comment,
)


def main() -> int:
    failures: list[str] = []

    def check(step: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} - {step}" + ("" if ok else f": {detail}"))
        if not ok:
            failures.append(step)

    verdicts = [
        AgentVerdict("triage", "triage-x", "bug", 0.9, {"v": "bug"}, "t1"),
        AgentVerdict("pr_review", "pr-x", "approve", 0.55, {"v": "approve"}, "t2"),
        AgentVerdict("security", "sec-x", "high", 0.88, {"v": "high"}, "t3"),
    ]

    result = evaluate_consensus(verdicts)
    print("evaluate_consensus result:")
    for k, v in result.items():
        if not k.startswith("_"):
            print(f"  {k}: {v}")

    check(
        "disagreement_detected is True (delta highest-lowest > 0.3)",
        result["disagreement_detected"] is True,
        f"delta={result['confidence_delta']}",
    )

    comment = format_disagreement_comment(result)
    print("\nformatted disagreement comment:\n", comment)

    n_sentences = comment.count(". ") + (1 if comment.strip().endswith(".") else 0)
    check("comment is 1 to 4 sentences", 1 <= n_sentences <= 4, f"sentences={n_sentences}")
    check("comment has no bullet points", ("- " not in comment and "* " not in comment))
    check("comment has no em dashes", "—" not in comment and "–" not in comment)
    check("comment has no markdown headers", "#" not in comment)

    print("-" * 60)
    if failures:
        print(f"Phase 5 FAILED. {len(failures)} check(s) failed: {failures}")
        return 1
    print("Phase 5 consensus layer verified. All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
