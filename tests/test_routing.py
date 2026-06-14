"""Routing tests for the OpenHive LangGraph entry point.

These cover the core decision that determines which agent handles each GitHub
event. They run with zero Claude calls, zero GitHub calls, zero Supabase calls,
and zero ChromaDB writes: route_event is pure logic over a mocked payload.

Run:  python -m pytest tests/ -v
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.graph import route_event  # noqa: E402


def test_issues_event_routes_to_triage():
    payload = {
        "action": "opened",
        "issue": {"number": 1, "title": "Test issue", "body": "Test body"},
        "repository": {"full_name": "test/repo"},
    }
    assert route_event({"event_type": "issues", "payload": payload}) == "triage"


def test_push_dependency_file_routes_to_security():
    payload = {
        "commits": [{"modified": ["requirements.txt"]}],
        "ref": "refs/heads/main",
    }
    assert route_event({"event_type": "push", "payload": payload}) == "security"


def test_push_doc_file_routes_to_docs():
    payload = {
        "commits": [{"modified": ["README.md"]}],
        "ref": "refs/heads/main",
    }
    assert route_event({"event_type": "push", "payload": payload}) == "docs"


def test_pull_request_event_routes_to_pr_review():
    payload = {
        "action": "opened",
        "pull_request": {"number": 1},
        "repository": {"full_name": "test/repo"},
    }
    assert route_event({"event_type": "pull_request", "payload": payload}) == "pr_review"


def test_unknown_event_routes_to_noop():
    assert route_event({"event_type": "marketplace_purchase", "payload": {}}) == "noop"
