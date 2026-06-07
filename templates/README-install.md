# Installing OpenHive on your repository

OpenHive is a swarm of AI agents that works like a senior engineering team for your open source project. It triages new issues, reviews pull requests, scans your dependencies for known vulnerabilities and opens patch PRs, watches your documentation, tracks your repository's health, and every morning posts a single plain-English digest of everything it found. You stay the maintainer; OpenHive does the tireless first pass so nothing slips through.

## Install in 5 steps (under 5 minutes, any public GitHub repo)

1. Create an account and connect your repository at the OpenHive site: https://openhive-backend.onrender.com
2. Add two secrets to your repository under Settings, then Secrets and variables, then Actions:
   - `OPENHIVE_BACKEND_URL` — your OpenHive backend address (e.g. `https://openhive-backend.onrender.com`)
   - `OPENHIVE_WEBHOOK_SECRET` — the shared signing secret from OpenHive (or any long random string set on both sides)
3. Copy `openhive-action.yml` into your repository at `.github/workflows/openhive.yml`.
4. Push any change to your repository to trigger the first run.
5. Within two minutes, check your repository's Issues or Discussions tab for your first OpenHive report.

Installation takes under five minutes and works on any public GitHub repository.
