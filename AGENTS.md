# OpenHive Agents

This document describes the exact decision boundary of each agent in the swarm. It exists so that contributors and maintainers understand how to trust the agents, where their limits are, and how to extend them safely. Every agent makes at most one Claude call per event, under a hard token ceiling, and only when a real GitHub event fires.

## Triage Agent

The Triage Agent wakes when an issue is opened. It reads the issue title and body, classifies the issue as a bug, a feature request, a duplicate, or invalid, and posts a single structured comment that asks the clarifying questions a senior engineer would ask before touching the code. It writes its verdict to shared memory and persists it to the audit log before it ever writes to GitHub.

It does not modify code, close issues, or apply labels automatically, and it deliberately skips any issue that OpenHive itself generated, such as a health report or a digest, so the swarm never triages its own output. That boundary exists because triage is a judgment surface meant for human contributions, and acting on its own posts would create noise and feedback loops. Its Claude call is capped at 400 tokens. Confidence is a float between 0 and 1 that Claude returns alongside the classification, reflecting how clearly the issue maps to a single category.

## PR Review Agent

The PR Review Agent wakes when a pull request is opened, reopened, or updated. It fetches the diff, truncates it to a fixed window for cost control, and reviews it for correctness, breaking changes, missing test coverage, and the distance between what the description claims and what the code actually does. It posts a review comment written in the voice of a careful staff engineer.

It does not approve or merge pull requests, and it never reviews OpenHive's own automated patch pull requests, identified by their branch prefix, so the Security Agent's output is not reviewed by another agent in a loop. That boundary keeps the agent advisory rather than authoritative, which is the correct posture for a tool that assists a human maintainer rather than replacing their merge decision. Its Claude call is capped at 600 tokens because structured review output is larger than a triage classification. Confidence is a float between 0 and 1 returned by Claude, expressing how sure it is about its verdict of approve, request changes, or comment.

## Security Agent

The Security Agent wakes on a push to the default branch that modifies a dependency manifest such as requirements.txt or package.json. It reads the changed manifest, queries the OSV vulnerability database for each pinned package, and if it finds known vulnerabilities it calls Claude for a structured remediation plan and opens a patch pull request that upgrades the affected packages. If the scan is clean it records a clean bill of health and stops without calling Claude at all.

It only acts on pushes to the default branch, never on feature branches, which prevents the patch pull request it opens from re-triggering itself in an endless loop. It also does not delete or downgrade packages or touch application code beyond the manifest. That boundary exists because dependency remediation must be reversible, reviewable, and confined to a clear surface the maintainer can reason about. Its Claude call is capped at 500 tokens and fires only when vulnerabilities exist, so a clean repository costs zero model tokens. Severity is summarized by Claude as critical, high, medium, or low across all findings rather than a numeric confidence.

## Docs Agent

The Docs Agent wakes on a push to the default branch that modifies a Python, JavaScript, TypeScript, or Markdown file, or a changelog. It reads up to three changed files, identifies the most important documentation gap such as a missing docstring or a stale README section, and posts a commit comment proposing the specific fix.

It only acts on the default branch and only on documentation-relevant files, which is a deliberately narrow trigger that prevents it from reacting to every push and flooding the repository with comments. It does not rewrite files or open pull requests, because documentation suggestions are most useful as lightweight prompts the maintainer can accept on their own terms. Its Claude call is capped at 300 tokens, the smallest ceiling in the swarm, because gap detection needs only a short structured answer. It reports a boolean for whether a gap was found rather than a numeric confidence.

## Health Agent

The Health Agent runs on a schedule rather than a single event. It gathers repository vitals including open issues, open pull requests, commit volume over the last thirty days, unique contributors in that window, the most recent commit date, and the count of stale branches, and it asks Claude to turn those metrics into a health score from zero to one hundred with a label of thriving, stable, slowing, or at risk, a single key insight, and one recommended action. It posts the result as a GitHub Discussion, falling back to a labeled issue if Discussions are not enabled.

It does not act on individual events or modify the repository in any way beyond posting its report, because its job is observation and honest reporting rather than intervention. That boundary keeps it a trusted mirror of the project's trajectory. Its Claude call is capped at 400 tokens. Its confidence is expressed as the health score itself divided by one hundred, since the score is the agent's calibrated judgment of repository vitality.

## Transparent Disagreement Protocol

The consensus layer is not an agent but a protocol that runs after every event. It gathers the current verdict together with the swarm's recent verdicts for the same repository, pulled from the audit log over the past forty eight hours, and compares the confidence the agents place in their positions. When the difference between the highest and lowest confidence exceeds a threshold of 0.3, a disagreement is declared.

When a disagreement is detected the protocol does three things. It logs the conflict to the audit log with both positions named and the confidence delta recorded. It composes a plain English summary that names the two diverging agents and their views. And it appends that summary to the agent comment that is about to be posted, so the disagreement is visible to anyone reading the issue or pull request, not only to someone reading server logs. The cross-agent enrichment that makes this possible reads the most recent verdict per real agent, excluding the derived consensus and digest records, so the comparison is always between genuine opinions.

The protocol deliberately surfaces conflict rather than resolving it automatically. Averaging two disagreeing agents into a single muted verdict would hide exactly the signal a maintainer most needs to see. By naming the disagreement and handing the decision back to the human with both positions stated clearly, OpenHive treats the maintainer as the final authority and the swarm as a team that reasons in the open.
