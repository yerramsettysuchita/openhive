<div align="center">

# 🐝 OpenHive

### A swarm of AI agents that maintains your open source project while you sleep.

*A swarm that thinks. A protocol that argues. A digest that decides.*

**Built for the people who built the internet and never got a team.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-orchestration-FF6F00.svg)](https://langchain-ai.github.io/langgraph/)
[![Claude Sonnet](https://img.shields.io/badge/Claude-Sonnet%204.6-D97757.svg)](https://www.anthropic.com/)
[![GitHub Models](https://img.shields.io/badge/GitHub%20Models-observability-181717?logo=github&logoColor=white)](https://github.com/marketplace/models)
[![Deploy: Render](https://img.shields.io/badge/Backend-Render-46E3B7.svg)](https://render.com/)
[![Dashboard: Vercel](https://img.shields.io/badge/Dashboard-Vercel-000000?logo=vercel&logoColor=white)](https://openhive-omega.vercel.app)

**Live backend:** https://openhive-backend.onrender.com  
**Frontend dashboard:** https://openhive-omega.vercel.app  
**Test repository:** https://github.com/yerramsettysuchita/openhive-test  

**[Live Backend](https://openhive-backend.onrender.com/health) · [Live Dashboard](https://openhive-omega.vercel.app) · [Install in 5 minutes](#install-openhive-on-your-repo) · [How it works](#how-it-works) · [See it in action](#see-it-in-action)**

</div>

<br>

## The problem nobody is solving

There are over 28 million public repositories on GitHub. The median active open source project has one maintainer. That one person is triaging issues, reviewing pull requests, hunting vulnerabilities, writing documentation, and tracking project health simultaneously, unpaid, and invisible to the users who depend on their work.

Every tool that exists today was built for the wrong person. Dependabot, label bots, GitHub Copilot they help contributors write code. Nothing was built to give the maintainer a team.

That is the gap OpenHive closes. It treats the maintainer as the primary user and wraps an intelligent engineering team around them, installed as a single GitHub Action, living where the work already lives.

<br>

## What OpenHive does

Add one YAML file and one secret to any public repository. From that moment a swarm of five specialized AI agents wakes up on every meaningful event. An issue opened. A pull request arriving. A dependency file changing. The swarm reads it, reasons about it, debates internally through a consensus protocol that surfaces disagreements rather than hiding them, and acts on it before the maintainer has finished their morning coffee.

<br>

## The five agents

| Agent | Wakes on | What it actually does |
|---|---|---|
| 🔎 Triage | Issue opened | Classifies bug, feature, duplicate, or invalid. Posts a structured comment and asks the exact clarifying questions a senior engineer would ask before touching the code |
| 👀 PR Review | PR opened or updated | Checks correctness, breaking changes, test coverage gaps, and the distance between what the PR claims and what the diff actually does |
| 🛡️ Security | Push touching a dependency file | Checks every dependency against the OSV database. On a CVE it does not just flag it. It opens a patch PR |
| 📚 Docs | Push touching .py, .js, .ts, or .md files | Spots missing docstrings, stale README sections, and lagging changelog entries, then proposes the fix as a commit comment |
| 📈 Health | Daily schedule | Tracks contributor activity, resolution velocity, branch staleness, and bus factor risk into a single health score from zero to one hundred |

<br>

## What makes OpenHive architecturally different

Most agent systems pipeline silently. OpenHive does three things no other maintainer tool does today.

### Shared memory: The swarm has a collective brain

Every finding from every agent flows into a ChromaDB memory layer, namespaced per agent so no agent's write can corrupt another's read. When the Security Agent flags a vulnerability, the PR Review Agent already knows about it before it reads the next diff. When the Triage Agent identifies a recurring bug pattern across twenty issues, the Health Agent folds that signal into its vitality score. The agents share context the way a real team does, through a common understanding of what is happening in the repository right now.

### Transparent Disagreement Protocol: It argues in the open

When two agents reach different conclusions about the same repository, and the confidence delta between their positions exceeds 0.3, the disagreement is not hidden or averaged away. It is logged, named, and surfaced to the maintainer with both positions stated clearly in plain English. The maintainer makes the call with full information.

This fires on real events. Every event is evaluated against the swarm's recent memory of the repository. In a live test, a single issue produced five cross-agent verdicts and surfaced a genuine disagreement between the PR Review Agent and the Health Agent, logged and persisted, not swept under a rug. No other agent system in production surfaces its own internal conflict to the user today.

### The Daily Digest: The interface is the digest

Once a day the swarm posts a single GitHub Discussion, not an email, not a Slack notification, not a new dashboard to learn. It ranks every finding from the past twenty four hours by severity and tells the maintainer in plain language exactly what needs their attention and what the swarm has already handled. The swarm lives where the work lives.

<br>

## How it works

```
                                                                                
  ┌─────────────────┐                                                           
  │  GitHub Event   │                                                           
  │ issue  PR push  │                                                           
  │   schedule      │                                                           
  └────────┬────────┘                                                           
           │  HMAC verified                                                     
           ▼                                                                    
  ┌─────────────────┐                                                           
  │    FastAPI      │                                                           
  │    /webhook     │                                                           
  │     Render      │                                                           
  └────────┬────────┘                                                           
           │                                                                    
           ▼                                                                    
  ┌─────────────────────────────────────────────────────────────────┐          
  │  LangGraph Agent Graph                                          │          
  │                                                                 │          
  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │          
  │   │   Triage    │  │  PR Review  │  │  Security   │             │          
  │   │   Agent     │  │   Agent     │  │   Agent     │             │          
  │   └──────┬──────┘  └──────┬──────┘  └───────┬─────┘             │          
  │          │                │                 │                   │          
  │   ┌─────────────┐  ┌─────────────┐          │                   │          
  │   │    Docs     │  │   Health    │          │                   │          
  │   │   Agent     │  │   Agent     │          │                   │          
  │   └──────┬──────┘  └──────┬──────┘          │                   │          
  │          │                │                 │                   │          
  │          └────────────────┴─────────────────┘                   │          
  │                           │                                     │          
  │                           ▼                                     │          
  │              ┌────────────────────────┐                         │          
  │              │    consensus_check     │                         │          
  │              │  Disagreement Protocol │                         │          
  │              │ cross-agent enrichment │                         │          
  │              └────────────┬───────────┘                         │          
  │                           │                                     │          
  └───────────────────────────┼─────────────────────────────────────┘          
                              │                                                 
           ┌──────────────────┼──────────────────┐                             
           │                  │                  │                             
           ▼                  ▼                  ▼                             
  ┌─────────────────┐ ┌───────────────┐ ┌────────────────┐                    
  │  Claude Sonnet  │ │   ChromaDB    │ │   Supabase     │                    
  │  per-agent call │ │ shared memory │ │  verdict log   │                    
  │  max_tokens cap │ │  namespaced   │ │ written BEFORE │                    
  └─────────────────┘ └───────────────┘ │  GitHub write  │                    
                                        └────────────────┘                    
                              │                                                 
                              ▼                                                 
  ┌─────────────────────────────────────────────────────────────────┐          
  │  GitHub Response                                                │          
  │                                                                 │          
  │   issue comment     PR review     patch PR     commit comment   │          
  │   health report     daily digest posted to Discussions          │          
  └─────────────────────────────────────────────────────────────────┘          

```
A GitHub event hits the webhook endpoint. The HMAC signature is verified before anything runs.

LangGraph routes the event to exactly one of five agent nodes with per-event state isolation so concurrent webhook events never corrupt each other.

The agent makes one Claude Sonnet 4.6 call under a strict token budget, writes its finding to ChromaDB, and persists a verdict to Supabase before any GitHub write, so nothing unauditable ever ships.

The consensus_check node pulls the swarm's recent verdicts for that repository from Supabase and runs the Disagreement Protocol across the full cross-agent picture.

The agent posts a human-sounding response back to GitHub. Once a day the Daily Digest summarizes everything into a single morning note.

<br>

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI on Render | Async, typed, deploys from render.yaml in minutes |
| Orchestration | LangGraph | Agents as nodes, decisions as edges, isolated per-event state |
| Reasoning | Claude Sonnet 4.6 | One distinct system prompt, voice, and decision boundary per agent |
| Microsoft stack | GitHub Models via gpt-4o-mini | Every Claude call wrapped with a GitHub Models trace using the Azure AI Inference SDK |
| Shared memory | ChromaDB | Namespaced per-agent collections with local embeddings and zero API cost |
| Persistence | Supabase on PostgreSQL | Durable auditable verdict log with idempotency via unique finding_id |
| Frontend | Next.js on Vercel | Health score, activity feed, disagreement log, and digest archive |
| Distribution | GitHub Action | One YAML file, one secret, any public repository |

<br>

## See it in action

Every example below is a real output from a live OpenHive deployment on a test repository. No mockups.

**Triage Agent** classifying a real bug report with confidence 0.92:

> Thanks for flagging this. It does look like a real bug and I want to get it reproduced properly before we touch the code. A few things would help move this forward. Does this occur in other browsers or is it specific to Chrome 120? Are there any errors in the browser console when the Login button is clicked after the session timeout? Is the timeout happening on the client side before the request fires, or is the server responding with a session error?

**PR Review Agent** catching a false coverage claim with verdict request_changes:

> This PR adds two utility functions but the description claims complete unit test coverage and docstrings for all functions. The diff contains zero test files and zero docstrings, so both claims are false. The multiply implementation also silently breaks for negative or float values of b due to the loop approach. The contributor should add docstrings to both functions, a test file covering normal and edge cases, and update the description to accurately reflect what the PR actually contains.

**Security Agent** opening a real patch PR after finding seven CVEs in requests 2.6.0:

> This PR upgrades requests from 2.6.0 to 2.32.3 to remediate seven known CVEs. CVE-2018-18074 involves an auth header leak on HTTPS to HTTP redirects. CVE-2024-47081 involves a .netrc credential leak on malformed URLs. The remaining five CVEs cover redirect handling and session fixation vectors. All changes are confined to requirements.txt and no application code requires modification.

**Daily Digest** as a real morning note pulling from all five agents:

> The repository is in a rough spot today with a health score of 42 and clear signs of stagnation. Six findings came in over the last 24 hours and three of them need attention now. Security found a critical open PR that upgrades requests to fix seven CVEs. PR Review found a pull request whose description claims test coverage the diff does not contain. Consensus flagged a disagreement between the PR Review and Health agents about the repository trajectory. Merge the security upgrade today. Block the PR with the false coverage claims and ask the contributor to add tests before it moves forward.

**Transparent Disagreement Protocol** firing live on a real event with five cross-agent verdicts:

> The swarm is not fully aligned on this one. The PR Review Agent is highly confident this pull request needs changes before merging, while the Health Agent sees the repository as already slowing and is more cautious about blocking contributions. A look at the specific test coverage gaps the PR Review Agent flagged would help resolve this. The diff shows real functionality being added and that matters for a slowing project, but shipping without tests creates a different kind of debt.

<br>

## Token discipline

OpenHive is engineered to be cheap enough to run continuously. Every agent makes at most one Claude call per event, each under a hard max_tokens ceiling, and only when a real event fires, never in polling loops or test cycles.

| Agent | max_tokens cap | Observed live |
|---|---|---|
| Triage | 400 | 244 input, 193 output |
| PR Review | 600 | 370 input, 175 output |
| Security | 500 | 702 input, 333 output |
| Docs | 300 | 179 input, 78 output |
| Health | 400 | 220 input, 114 output |
| Digest | 500 | 724 input, 294 output |

The Security Agent only calls Claude when vulnerabilities actually exist. A clean dependency scan costs zero model tokens. The Docs Agent only calls Claude when documentation-relevant files are modified. The consensus layer is pure Python weighted voting with no model calls.

<br>

## Install OpenHive on your repo

OpenHive installs into any public GitHub repository in under five minutes.

**Step 1**: Go to your repository Settings, then Secrets and variables, then Actions. Add two secrets. OPENHIVE_BACKEND_URL should be set to the live backend URL shown above. OPENHIVE_WEBHOOK_SECRET should be set to a random 32-character hex string which you can generate by running the following command in any terminal:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Step 2**: Copy the file at templates/openhive-action.yml from this repository into your repository at .github/workflows/openhive.yml.

**Step 3**: Push any change to your repository to trigger the first run.

**Step 4**: Check your repository Issues or Discussions tab within two minutes for your first OpenHive report.

That is the complete installation. OpenHive will now respond to every issue, pull request, dependency change, and scheduled health check in your repository automatically. Full installation guide is at templates/README-install.md.

<br>

## Run it yourself locally

Prerequisites are Python 3.12, Git, and ngrok for exposing your local server to GitHub webhooks. Python 3.14 is not supported because several dependencies ship C-extension wheels only for 3.12.

```bash
git clone https://github.com/yerramsettysuchita/openhive.git
cd openhive

py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env
```

Fill in the required environment variables in your .env file, then start the server:

```bash
uvicorn backend.main:app --reload --port 8000
```

In a second terminal start an ngrok tunnel:

```bash
ngrok http 8000
```

Register the ngrok HTTPS URL followed by /webhook as a webhook on any public GitHub repository you control. Set content type to application/json, the secret to your GITHUB_WEBHOOK_SECRET value, and select Issues, Pull requests, and Pushes as the event triggers.

Open an issue on that repository. Within thirty seconds you will see the Triage Agent classify it in your terminal and post a comment on the issue.

To trigger the daily digest manually:

```bash
curl -X POST "http://localhost:8000/digest?repo=owner/your-repo-name"
```

<br>

## Environment variables

| Variable | Required | What it does |
|---|---|---|
| ANTHROPIC_API_KEY | Yes | Claude Sonnet inference for all five agents |
| GITHUB_TOKEN | Yes | GitHub Models observability tracing via Azure AI Inference SDK |
| GITHUB_TOKEN_REPO | Yes | PyGitHub writes for comments, labels, and patch PRs. Requires repo and workflow scopes |
| GITHUB_MODELS_ENDPOINT | Yes | Set to https://models.github.ai/inference |
| GITHUB_WEBHOOK_SECRET | Yes | HMAC verification of all incoming GitHub webhook payloads |
| SUPABASE_URL | Yes | Supabase project URL for verdict persistence |
| SUPABASE_KEY | Yes | Supabase anon key for verdict persistence |
| RAILWAY_ENV | No | Set to production on Render. Defaults to local |

See .env.example for the fully commented variable set with notes on which phase introduced each one.

<br>

## Supabase schema

Run the following in your Supabase SQL editor before starting the backend for the first time:

```sql
create table if not exists agent_verdicts (
  id uuid default gen_random_uuid() primary key,
  created_at timestamptz default now(),
  repo_full_name text not null,
  event_type text not null,
  agent_name text not null,
  finding_id text not null unique,
  classification text,
  confidence float,
  raw_response jsonb not null,
  github_action_taken text,
  github_action_url text,
  error_occurred boolean default false,
  error_message text
);

create index if not exists idx_verdicts_repo on agent_verdicts(repo_full_name);
create index if not exists idx_verdicts_agent on agent_verdicts(agent_name);
create index if not exists idx_verdicts_created on agent_verdicts(created_at desc);
```

The finding_id column carries a unique constraint so duplicate webhook deliveries are rejected at the database level rather than producing duplicate agent actions.

<br>

## Repository layout

```
openhive/
├── backend/
│   ├── main.py              FastAPI app, /webhook, /digest, /health endpoints
│   ├── webhook_router.py    HMAC signature verification and graph entry point
│   ├── graph.py             LangGraph topology and consensus_check node
│   ├── persistence.py       Supabase interface for verdicts and idempotency
│   ├── digest.py            Daily Digest generator and GitHub post
│   └── tracer.py            GitHub Models observability wrapper
├── agents/
│   ├── triage.py            Issue classification and clarifying questions
│   ├── pr_review.py         Diff analysis and review comment
│   ├── security.py          OSV vulnerability scan and patch PR generation
│   ├── docs.py              Documentation gap detection and commit comment
│   └── health.py            Repository vitals and health score report
├── memory/
│   └── chroma_store.py      ChromaDB shared memory layer with per-agent namespacing
├── consensus/
│   └── protocol.py          Transparent Disagreement Protocol, pure Python
├── templates/
│   ├── openhive-action.yml  GitHub Action template shipped to maintainers
│   └── README-install.md    Five-step installation guide
├── supabase/
│   └── schema.sql           One table, three indexes, complete schema
├── render.yaml              Render Infrastructure as Code for one-click deploy
├── requirements.txt         All dependencies pinned for reproducible installs
└── .env.example             Fully commented environment variable template
```

The shipped Action at templates/openhive-action.yml is deliberately separate from OpenHive's own CI at .github/workflows/openhive-ci.yml so the repository never becomes self-referential during development and testing.

<br>

## Functional requirements

The system responds to GitHub issue creation events within ninety seconds of the webhook firing. The system responds to pull request events within one hundred and twenty seconds. The Security Agent checks dependencies against the OSV database on every push to the default branch that modifies a dependency file. The daily digest posts to GitHub Discussions at 8 AM UTC every day via the GitHub Action cron schedule. The disagreement protocol surfaces any conflict where the confidence delta across recent swarm verdicts for a repository exceeds 0.3. The GitHub Action works on any public repository with no modification beyond adding two secrets and one workflow file. The live prototype remains accessible and functional for a minimum of thirty days after submission.

<br>

## Non-functional requirements

Agent response latency does not exceed one hundred and twenty seconds for any single event under normal load. The system handles concurrent webhook events without race conditions through LangGraph per-event state isolation. The shared memory layer prevents cross-agent write corruption through ChromaDB collection namespacing where each agent writes only to its own openhive underscore agent_name collection. All agent verdicts are stored in Supabase before any GitHub API write is attempted, ensuring every action OpenHive takes is fully auditable. Missing Supabase connectivity logs a warning and continues rather than crashing the swarm. The codebase is fully open source under the MIT license with no dependency on any proprietary service that cannot be substituted with an open alternative. A developer who has never seen this project can have it running locally in under twenty minutes following this README.

<br>

## Design guarantees

Every verdict is written to Supabase before any GitHub write. If the persistence call fails the agent logs the failure and continues because the GitHub response matters more than the audit record during degraded conditions, but the failure is always surfaced in logs and never silently dropped.

LangGraph isolates state per event so two simultaneous webhook deliveries, say a PR and an issue arriving in the same second, process independently without either corrupting the other's state or memory writes.

The Security Agent only acts on default branch pushes. Agents never review or triage content that OpenHive itself generated. The Triage Agent carries an explicit guard that checks whether an issue was opened by the same account running OpenHive and skips it silently if so. This prevents the swarm from feeding back on its own daily digest or health reports.

The idempotency guarantee means that if GitHub delivers the same webhook event twice, the second delivery produces a database conflict on finding_id and the agent returns cleanly without duplicating any GitHub comment, label, or PR.

<br>

## Roadmap

Five agents live end to end on real GitHub events is complete. ChromaDB shared memory with cross-agent recall is complete. The Transparent Disagreement Protocol firing on live events is complete. The Daily Digest as a GitHub-native post is complete. One-file GitHub Action install and Render deployment is complete.

Next on the roadmap is the Next.js dashboard showing health scores, activity feeds, disagreement logs, and digest archives across all connected repositories from a single interface. After that is per-repository configurable agent policies and token budgets so maintainers can tune OpenHive's behavior to their project's culture and pace. Multi-tenant install flow with per-repository isolation comes after that, enabling OpenHive to serve thousands of repositories from a single deployment without any repository's data touching another's.

Azure AI Foundry is the intended production upgrade for the observability layer. The tracer.py architecture accepts a Foundry endpoint and key as drop-in replacements for the current GitHub Models configuration. A funded Azure subscription activates this upgrade with two environment variable changes and zero code modifications.

<br>

## License

MIT. OpenHive depends on no proprietary service that cannot be substituted. Use it, fork it, build on it, ship it. If you improve it, consider opening a pull request.

<br>

<div align="center">

**OpenHive**: A swarm that thinks, a protocol that argues, a digest that decides.

Built for the Microsoft Build AI 2026 hackathon by Suchita Yerramsetty.

*This product is dedicated to every open source maintainer who has ever closed their laptop at midnight with two hundred unread issues and wondered if anyone noticed the work they were doing. Someone noticed.*

</div>
