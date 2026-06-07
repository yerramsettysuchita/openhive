# Contributing to OpenHive

Thank you for considering a contribution. OpenHive is built for open source maintainers, the people doing the work of ten with the tooling of none. Contributions from people who understand that world, who have triaged issues at midnight and reviewed pull requests on a Sunday, are especially welcome here. Everything in this project exists to give those people a team.

## Getting started

Local setup takes about fifteen minutes and is described in full in the [README](README.md). The three prerequisites are Python 3.12, a GitHub account, and an Anthropic API key. Once those are in place, clone the repo, create a virtual environment, install the requirements, and copy `.env.example` to `.env` to fill in your keys.

## What to contribute

There are four areas where help moves OpenHive forward the most. The first is new agent ideas for repository event types the swarm does not yet cover, such as release events, discussion threads, or stale issue sweeps. The second is improvements to the existing agent system prompts that measurably improve classification accuracy or make the agents sound more human. The third is frontend dashboard features for the Next.js application, like filtering the activity feed by agent or charting health over time. The fourth is documentation improvements to the installation guide so the next maintainer gets running even faster.

## How to submit

Fork the repository and create a branch named `feature/your-feature-name`. Make your changes, and include a test that confirms the change works the way you intend. Open a pull request against `main` with a description that explains what the change does and, just as important, why it makes OpenHive better for maintainers. Pull requests that connect a change to a real maintainer pain point are reviewed fastest.

## Agent token budgets

Every agent operates under a per-agent `max_tokens` ceiling defined in the codebase, because OpenHive is designed to run affordably across many repositories. Any change that increases token usage must include a clear justification in the pull request description explaining why the additional budget is necessary and what the maintainer gets in return. Changes that reduce token usage while preserving quality are always welcome.

## Code of conduct

This project follows the Contributor Covenant code of conduct, and we expect everyone who participates to help keep it a welcoming place. Harassment or exclusionary behavior of any kind will result in removal from the project.
