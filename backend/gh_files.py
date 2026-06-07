"""Robust changed-file detection for push events.

A raw GitHub webhook populates commits[].added/modified. But a push forwarded
through the GitHub Action via toJSON(github.event) can arrive with those arrays
empty, which caused the Security and Docs agents to silently skip. This helper
adds a three-tier fallback so detection works on both paths:

  1. commits[].added/modified/removed (and head_commit)
  2. head_commit.added/modified/removed
  3. GitHub compare API between payload.before and payload.after

The result is cached on the payload dict so the compare call fires at most once
per event even though several callers ask for it.
"""

import os

_CACHE_KEY = "_openhive_changed_files"


def changed_files(payload: dict) -> set:
    if not isinstance(payload, dict):
        return set()
    if _CACHE_KEY in payload:
        return payload[_CACHE_KEY]

    files: set[str] = set()

    # Tier 1 + 2: commits and head_commit.
    commits = list(payload.get("commits", []) or [])
    head = payload.get("head_commit")
    if head:
        commits.append(head)
    for c in commits:
        if not isinstance(c, dict):
            continue
        for key in ("added", "modified", "removed"):
            for f in c.get(key, []) or []:
                files.add(f)

    # Tier 3: compare before..after via the GitHub API.
    if not files:
        before = payload.get("before")
        after = payload.get("after")
        repo_full = (payload.get("repository") or {}).get("full_name")
        zero = "0000000000000000000000000000000000000000"
        if before and after and repo_full and before != zero and after != zero:
            try:
                from github import Github

                g = Github(os.getenv("GITHUB_TOKEN_REPO"))
                comparison = g.get_repo(repo_full).compare(before, after)
                for f in comparison.files:
                    files.add(f.filename)
            except Exception as exc:  # noqa: BLE001
                print(f"[OPENHIVE] changed_files compare fallback failed: {exc}")

    payload[_CACHE_KEY] = files
    return files
