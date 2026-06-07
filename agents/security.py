"""Security Agent — Phase 4 (third fully working agent).

Flow per push event:
  1. Default-branch + dependency-file guard (scoped trigger).
  2. Fetch the modified dependency file contents at the pushed SHA.
  3. Query the OSV database per package.
  4. No vulns -> clean bill of health to ChromaDB, no Claude, no GitHub write.
  5. Vulns -> one Claude call (claude-sonnet-4-6, max_tokens=500) -> remediation.
  6. Parse JSON.
  7. save_verdict to Supabase BEFORE any GitHub write.
  8. Write finding to ChromaDB.
  9. Open a real patch PR (new branch, bumped versions, PR body from Claude).
 10. Update and return state.

GUARD: only pushes to the DEFAULT branch are processed. The patch PR is pushed
to a feature branch (openhive-security-patch-*); without this guard that push
would re-trigger the Security Agent in a loop.

TOKEN DISCIPLINE: Claude is called ONLY when vulnerabilities exist, capped at
500 output tokens. OSV lookups and a clean scan cost zero model tokens.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from anthropic import Anthropic
from github import Github

from backend.persistence import save_verdict
from backend.gh_files import changed_files
from memory.chroma_store import write_finding

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 500
OSV_URL = "https://api.osv.dev/v1/query"
MAX_PACKAGES_PER_FILE = 20

QUALIFYING_FILES = {
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "pyproject.toml",
    "yarn.lock",
    "go.mod",
}

SECURITY_SYSTEM_PROMPT = (
    "You are the Security Agent for OpenHive, an AI maintainer assistant. You "
    "have been given a list of vulnerabilities found in this repository's "
    "dependency files. Your only job is to produce a structured remediation "
    "plan. You must respond with a valid JSON object and nothing else. The JSON "
    "must have exactly three fields. severity_summary is one of critical, high, "
    "medium, or low representing the overall severity across all findings. "
    "remediation_steps is a list of objects each containing package_name, "
    "current_version, recommended_version, and action where action is one of "
    "upgrade, replace, or monitor. pr_description is a string of three to five "
    "sentences written as a senior engineer would write them describing what "
    "the patch PR will do and why each change is necessary. Do not write "
    "anything outside the JSON object."
)

_anthropic_client: Optional[Anthropic] = None
_github_client: Optional[Github] = None


def _client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


def _github() -> Github:
    global _github_client
    if _github_client is None:
        token = os.getenv("GITHUB_TOKEN_REPO")
        if not token:
            raise ValueError("GITHUB_TOKEN_REPO not set")
        _github_client = Github(token)
    return _github_client


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _changed_dep_files(payload: dict) -> list[str]:
    # Uses the shared three-tier detector (commits -> head_commit -> compare API)
    # so it works for raw webhooks and GitHub Action toJSON(github.event) pushes.
    return sorted(f for f in changed_files(payload) if os.path.basename(f) in QUALIFYING_FILES)


def _parse_requirements(content: str) -> list[tuple[str, str]]:
    """Return (package, version) pairs from a requirements.txt body."""
    out = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-]+)", s)
        if m:
            out.append((m.group(1), m.group(2)))
    return out[:MAX_PACKAGES_PER_FILE]


def _parse_package_json(content: str) -> list[tuple[str, str]]:
    out = []
    try:
        data = json.loads(content)
    except Exception:  # noqa: BLE001
        return out
    deps = {}
    deps.update(data.get("dependencies", {}) or {})
    deps.update(data.get("devDependencies", {}) or {})
    for name, ver in deps.items():
        clean = re.sub(r"^[\^~>=<\s]+", "", str(ver))
        if clean:
            out.append((name, clean))
    return out[:MAX_PACKAGES_PER_FILE]


def _osv_query(name: str, version: str, ecosystem: str) -> list[dict]:
    body = {"version": version, "package": {"name": name, "ecosystem": ecosystem}}
    try:
        r = httpx.post(OSV_URL, json=body, timeout=10.0)
        r.raise_for_status()
        vulns = r.json().get("vulns", []) or []
    except Exception as exc:  # noqa: BLE001
        print(f"[OPENHIVE] OSV query failed for {name}=={version}: {exc}")
        return []
    found = []
    for v in vulns:
        aliases = v.get("aliases", []) or []
        cve = next((a for a in aliases if a.startswith("CVE")), v.get("id", ""))
        sev = ""
        if v.get("severity"):
            sev = v["severity"][0].get("score", "") if v["severity"] else ""
        found.append(
            {
                "package": name,
                "version": version,
                "id": v.get("id", ""),
                "cve": cve,
                "severity": sev,
                "summary": (v.get("summary") or v.get("details", ""))[:160],
            }
        )
    return found


def security_node(state: dict) -> dict:
    payload = state.get("payload", {})
    repo_full_name = state.get("repo_full_name") or payload.get("repository", {}).get("full_name")
    default_branch = payload.get("repository", {}).get("default_branch", "main")
    ref = payload.get("ref", "")
    sha = payload.get("after") or (payload.get("head_commit") or {}).get("id", "")

    # Step 1: scoped trigger — default branch + dependency files only.
    if ref and ref != f"refs/heads/{default_branch}":
        print(f"[OPENHIVE] Security Agent: push to {ref} is not the default branch, skipping.")
        return {"agent_called": "security"}

    dep_files = _changed_dep_files(payload)
    if not dep_files:
        print("[OPENHIVE] Security Agent: no dependency files in this push, skipping.")
        return {"agent_called": "security"}

    print(f"[OPENHIVE] Security Agent called for files: {dep_files}")
    repo = _github().get_repo(repo_full_name)

    # Step 2: fetch each dependency file's content at the pushed SHA.
    file_blobs: dict[str, dict] = {}
    for path in dep_files:
        try:
            cf = repo.get_contents(path, ref=sha or default_branch)
            file_blobs[path] = {"content": cf.decoded_content.decode("utf-8"), "sha": cf.sha}
        except Exception as exc:  # noqa: BLE001
            print(f"[OPENHIVE] Could not fetch {path}: {exc}")

    # Step 3: OSV scan.
    vulnerabilities: list[dict] = []
    for path, blob in file_blobs.items():
        base = os.path.basename(path)
        if base == "requirements.txt":
            pkgs = _parse_requirements(blob["content"])
            eco = "PyPI"
        elif base == "package.json":
            pkgs = _parse_package_json(blob["content"])
            eco = "npm"
        else:
            pkgs = []
            eco = ""
        for name, ver in pkgs:
            print(f"[OPENHIVE] OSV check: {name}=={ver} ({eco})")
            vulnerabilities.extend(_osv_query(name, ver, eco))

    # Step 4: clean scan -> no Claude, no GitHub write.
    if not vulnerabilities:
        finding_id = f"security-{(sha or 'nosha')[:8]}"
        metadata = {
            "agent": "security",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repository": repo_full_name,
            "severity_summary": "none",
            "affected_packages": "",
        }
        write_finding("security", finding_id, "Clean bill of health: no known vulnerabilities.", metadata)
        print(f"[OPENHIVE] Security Agent: no vulnerabilities found. Memory: {finding_id}")
        return {"agent_called": "security", "findings": [{"id": finding_id, "metadata": metadata}]}

    print(f"[OPENHIVE] Security Agent: {len(vulnerabilities)} vulnerability finding(s).")

    # Step 5: Claude remediation plan (only when vulns exist).
    vuln_text = "\n".join(
        f"- {v['package']}=={v['version']} | {v['cve'] or v['id']} | severity {v['severity'] or 'n/a'} | {v['summary']}"
        for v in vulnerabilities
    )
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=SECURITY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Vulnerabilities found:\n{vuln_text}"}],
    )
    print(
        f"[TOKEN USE] security input={message.usage.input_tokens} "
        f"output={message.usage.output_tokens}"
    )
    raw = message.content[0].text
    print(f"[OPENHIVE] Claude remediation: {raw}")

    # Step 6: parse.
    try:
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        errors = list(state.get("errors", []))
        errors.append(f"security: failed to parse Claude JSON: {exc}")
        return {"errors": errors}

    severity = parsed.get("severity_summary", "unknown")
    steps = parsed.get("remediation_steps", []) or []
    pr_description = parsed.get("pr_description", "")
    affected = ", ".join(sorted({v["package"] for v in vulnerabilities}))
    sha8 = (sha or "nosha")[:8]
    finding_id = f"security-{sha8}"

    # Step 7: persist verdict BEFORE any GitHub write.
    saved = save_verdict(
        repo_full_name,
        "push",
        "security",
        finding_id,
        parsed,
        classification=severity,
        github_action_taken="opening_patch_pr",
    )
    if not saved:
        print("[PERSISTENCE] security verdict not saved, continuing anyway.")

    # Step 8: write finding to ChromaDB.
    metadata = {
        "agent": "security",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": repo_full_name,
        "severity_summary": severity,
        "affected_packages": affected,
    }
    write_finding("security", finding_id, raw, metadata)
    print(f"[OPENHIVE] Memory written: {finding_id}")

    # Step 9: open the patch PR.
    errors = list(state.get("errors", []))
    try:
        branch = f"openhive-security-patch-{sha8}"
        base = repo.get_branch(default_branch)
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base.commit.sha)

        upgrades = [s for s in steps if s.get("action") == "upgrade"]
        changed_count = 0
        for path, blob in file_blobs.items():
            if os.path.basename(path) != "requirements.txt":
                continue
            new_content = blob["content"]
            for s in upgrades:
                pkg = s.get("package_name", "")
                newv = s.get("recommended_version", "")
                if not pkg or not newv:
                    continue
                pattern = re.compile(
                    rf"^({re.escape(pkg)})\s*==\s*[A-Za-z0-9_.\-]+",
                    re.MULTILINE | re.IGNORECASE,
                )
                new_content, n = pattern.subn(rf"\1=={newv}", new_content)
                changed_count += n
            if new_content != blob["content"]:
                repo.update_file(
                    path,
                    f"OpenHive security patch: bump vulnerable packages in {path}",
                    new_content,
                    blob["sha"],
                    branch=branch,
                )

        n_pkgs = len({s.get("package_name") for s in upgrades if s.get("package_name")}) or len(steps)
        title = f"OpenHive Security Patch - {n_pkgs} packages ({severity})"
        pr_description = pr_description.replace("—", ", ").replace("–", ", ").replace(" , ", ", ").replace("  ", " ").strip()
        pr = repo.create_pull(title=title, body=pr_description, head=branch, base=default_branch)
        print(f"[OPENHIVE] Patch PR opened: {pr.html_url} ({changed_count} line(s) changed)")

        try:
            existing = {l.name for l in repo.get_labels()}
            if "security" in existing:
                pr.add_to_labels("security")
        except Exception as exc:  # noqa: BLE001
            print(f"[OPENHIVE] Could not apply 'security' label: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"security: failed to open patch PR: {exc}")
        print(f"[OPENHIVE] ERROR opening patch PR: {exc}")

    # Step 10: update state.
    finding = {"id": finding_id, "text": raw, "metadata": metadata, "severity": severity}
    return {"findings": [finding], "agent_called": "security", "errors": errors}
