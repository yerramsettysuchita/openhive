"""Generate OpenHive_deck.pdf — a 10-slide, 16:9 pitch deck in the OpenHive
editorial brand. Pure reportlab, no external services.

Run:  python scripts/build_deck.py
Output: OpenHive_deck.pdf at the project root.
"""

import os
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas

W, H = 1280, 720
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "OpenHive_deck.pdf")
FONTS = r"C:\Windows\Fonts"

# Colors
CREAM = HexColor("#FAF9F6")
WHITE = HexColor("#FFFFFF")
INK = HexColor("#1A1A18")
MUTED = HexColor("#6B6862")
BORDER = HexColor("#E7E3DA")
AMBER = HexColor("#D47C0F")
TEAL = HexColor("#0F7C6E")
RED = HexColor("#C23B22")
BLUE = HexColor("#1B5FA8")
GREEN = HexColor("#2E7D32")
PURPLE = HexColor("#7C3AED")


def _reg(name, filename):
    path = os.path.join(FONTS, filename)
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))
        return True
    return False


# Register fonts (fall back to built-ins if missing).
SERIF = "Georgia" if _reg("Georgia", "georgia.ttf") else "Times-Roman"
_reg("Georgia-Bold", "georgiab.ttf")
_reg("Georgia-Italic", "georgiai.ttf")
SANS = "Segoe" if _reg("Segoe", "segoeui.ttf") else "Helvetica"
_reg("Segoe-Bold", "segoeuib.ttf")
MONO = "Consola" if _reg("Consola", "consola.ttf") else "Courier"
SERIF_BOLD = "Georgia-Bold" if os.path.exists(os.path.join(FONTS, "georgiab.ttf")) else SERIF
SERIF_IT = "Georgia-Italic" if os.path.exists(os.path.join(FONTS, "georgiai.ttf")) else SERIF
SANS_BOLD = "Segoe-Bold" if os.path.exists(os.path.join(FONTS, "segoeuib.ttf")) else SANS

try:
    pdfmetrics.registerFontFamily("Segoe", normal="Segoe", bold=SANS_BOLD, italic="Segoe", boldItalic=SANS_BOLD)
except Exception:
    pass

MARGIN = 92
CW = W - 2 * MARGIN


def st(font, size, color, leading=None, align=TA_LEFT, space=0):
    return ParagraphStyle("s", fontName=font, fontSize=size, textColor=color,
                          leading=leading or size * 1.3, alignment=align, spaceAfter=space)


def para(c, text, style, x, y, width):
    p = Paragraph(text, style)
    _, h = p.wrap(width, 2000)
    p.drawOn(c, x, y - h)
    return h


def chrome(c, accent, n):
    c.setFillColor(CREAM); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(accent); c.rect(0, 0, 12, H, fill=1, stroke=0)
    # footer
    c.setStrokeColor(BORDER); c.setLineWidth(1); c.line(MARGIN, 58, W - MARGIN, 58)
    c.setFillColor(MUTED); c.setFont(MONO, 10)
    c.drawString(MARGIN, 40, "OpenHive  ·  a swarm that thinks, argues, decides")
    c.drawRightString(W - MARGIN, 40, f"{n:02d} / 10")


def header(c, accent, kicker, title, top=H - 96, tsize=42):
    c.setFillColor(accent); c.setFont(MONO, 13)
    c.drawString(MARGIN, top, kicker.upper())
    h = para(c, title, st(SERIF, tsize, INK, tsize * 1.08), MARGIN, top - 16, CW)
    return top - 16 - h - 30


def bullets(c, items, y, accent, size=16, gap=15, width=CW):
    s = st(SANS, size, INK, size * 1.42)
    for it in items:
        # colored dot
        c.setFillColor(accent); c.circle(MARGIN + 4, y - size + 4, 3.2, fill=1, stroke=0)
        h = para(c, it, s, MARGIN + 20, y, width - 20)
        y -= h + gap
    return y


def callout(c, text, y, accent, width=CW, italic=True, size=18):
    font = SERIF_IT if italic else SANS
    s = st(font, size, INK, size * 1.45)
    p = Paragraph(text, s)
    _, th = p.wrap(width - 56, 2000)
    boxh = th + 36
    c.setFillColor(WHITE); c.setStrokeColor(BORDER); c.setLineWidth(1)
    c.roundRect(MARGIN, y - boxh, width, boxh, 10, fill=1, stroke=1)
    c.setFillColor(accent); c.rect(MARGIN, y - boxh, 4, boxh, fill=1, stroke=0)
    p.drawOn(c, MARGIN + 28, y - boxh + 18)
    return y - boxh - 16


def lead(c, text, y, width=CW, size=19):
    return y - para(c, text, st(SANS, size, MUTED, size * 1.45), MARGIN, y, width) - 22


def b(t):
    return f"<b>{t}</b>"


c = canvas.Canvas(OUT, pagesize=(W, H))

# ---------- Slide 1 — Title ----------
chrome(c, AMBER, 1)
c.setFillColor(INK); c.roundRect(MARGIN, H - 250, 70, 70, 16, fill=1, stroke=0)
c.setFillColor(AMBER); c.setFont(SERIF_BOLD, 34); c.drawCentredString(MARGIN + 35, H - 234, "OH")
c.setFillColor(AMBER); c.setFont(MONO, 14); c.drawString(MARGIN, H - 290, "AI AGENTS  ·  OPEN SOURCE  ·  GITHUB-NATIVE")
c.setFillColor(INK); c.setFont(SERIF, 92); c.drawString(MARGIN - 4, H - 390, "OpenHive")
para(c, "A swarm of AI agents that maintains your open source project while you sleep.",
     st(SANS, 22, INK, 30), MARGIN, H - 410, 900)
para(c, "A swarm that thinks. A protocol that argues. A digest that decides.",
     st(SERIF_IT, 19, MUTED, 26), MARGIN, H - 470, 900)
c.setFillColor(MUTED); c.setFont(MONO, 12)
c.drawString(MARGIN, 150, "Live backend   https://openhive-backend.onrender.com")
c.drawString(MARGIN, 128, "Dashboard      https://openhive-omega.vercel.app")
c.drawString(MARGIN, 106, "Source         https://github.com/yerramsettysuchita/openhive")
c.showPage()

# ---------- Slide 2 — Problem ----------
chrome(c, RED, 2)
y = header(c, RED, "The problem", "Open source runs the world. One unpaid person runs each piece of it.", tsize=38)
y = bullets(c, [
    "There are over 28 million public repositories on GitHub. The median active project has exactly one maintainer.",
    "That one person triages issues, reviews pull requests, hunts vulnerabilities, writes docs, and tracks health, alone and unpaid.",
    f"Every tool today was built for the wrong person. Dependabot, label bots, and Copilot help {b('contributors write code')}. None gives the {b('maintainer')} a team.",
    "When the maintainer burns out, the project stalls, and everything built on top of it quietly inherits the risk.",
], y, RED, size=17, gap=18)
callout(c, "The tooling that exists was built for contributors. The maintainer, the person open source depends on most, was left to do the work of ten with the tools of none.",
        y - 6, RED)
c.showPage()

# ---------- Slide 3 — Solution ----------
chrome(c, AMBER, 3)
y = header(c, AMBER, "The solution", "One file. One secret. A team that never sleeps.")
y = lead(c, "Add a single GitHub Action to any public repo. From that moment a swarm of five specialized AI agents wakes on every meaningful event.", y)
y = bullets(c, [
    f"It {b('reads')} the event, {b('reasons')} about it with Claude, and {b('acts')}: comments, labels, patch PRs, and a daily digest.",
    "Agents share a common memory and debate their findings through a transparent consensus protocol.",
    "Everything happens where the work already lives: in the repo, on the issue, on the pull request.",
], y, AMBER, size=17, gap=18)
callout(c, "Installed in under five minutes. Works on any public GitHub repository. No new dashboard to learn.", y - 6, AMBER)
c.showPage()

# ---------- Slide 4 — Agents ----------
chrome(c, BLUE, 4)
y = header(c, BLUE, "The swarm", "Five specialized agents, one shared brain")
y = bullets(c, [
    f"{b('Triage')} — classifies every new issue as bug, feature, duplicate, or invalid, and asks the clarifying questions a senior engineer would ask.",
    f"{b('PR Review')} — checks correctness, breaking changes, test-coverage gaps, and the distance between what a PR claims and what the diff does.",
    f"{b('Security')} — scans dependencies against the OSV database and opens a patch PR when it finds a CVE, not just a flag.",
    f"{b('Docs')} — catches missing docstrings, stale README sections, and lagging changelogs, then proposes the fix.",
    f"{b('Health')} — scores contributor activity, resolution velocity, branch staleness, and bus-factor risk from 0 to 100.",
], y, BLUE, size=16, gap=16)
para(c, "Orchestrated by LangGraph: each agent is a node, each decision an edge, with isolated per-event state so concurrent webhooks never collide.",
     st(MONO, 12, MUTED, 18), MARGIN, y - 2, CW)
c.showPage()

# ---------- Slide 5 — Consensus ----------
chrome(c, PURPLE, 5)
y = header(c, PURPLE, "The differentiator", "The Transparent Disagreement Protocol")
y = lead(c, "Most agent systems pipeline silently. OpenHive argues in the open.", y)
y = bullets(c, [
    "When two agents diverge by more than 0.3 confidence, the conflict is logged, named, and surfaced, never averaged away.",
    "It fires on real events: every event is evaluated against the swarm's recent memory of the repository.",
    "The disagreement appears in the agent's own GitHub comment, where maintainers actually look.",
], y, PURPLE, size=16, gap=14)
y = callout(c, "One note before you act: the swarm is not fully aligned on this one. The Health Agent reads this repository differently than I do, so it is worth weighing both perspectives before deciding.",
            y - 2, PURPLE)
para(c, "No other agent system in production surfaces its own internal conflict to the user.",
     st(SANS_BOLD, 15, PURPLE, 21), MARGIN, y, CW)
c.showPage()

# ---------- Slide 6 — Microsoft stack ----------
chrome(c, TEAL, 6)
y = header(c, TEAL, "Microsoft stack", "GitHub-native, end to end")
y = bullets(c, [
    f"{b('GitHub Models')} (gpt-4o-mini) wraps every Claude call for observability tracing, the Microsoft-stack integration, authenticated with a GitHub token.",
    f"Distribution is a single {b('GitHub Action')}; events arrive through GitHub webhooks with verified HMAC signatures.",
    f"Outputs are GitHub-native: issue comments, labels, {b('patch PRs')}, and a daily {b('Discussion')} digest.",
    "There is no new platform to log into. The swarm lives inside GitHub, where maintainers already are.",
], y, TEAL, size=17, gap=18)
callout(c, "The Microsoft stack is satisfied honestly: every model decision is traced through GitHub Models, and the entire product ships and runs on GitHub.", y - 6, TEAL)
c.showPage()

# ---------- Slide 7 — Live proof ----------
chrome(c, GREEN, 7)
y = header(c, GREEN, "Live, not mocked", "Real agents. Real repository. Real outputs.", tsize=38)
y = callout(c, "Triage, on a real bug (confidence 0.92): “Thanks for flagging this. It does look like a real bug to me, and I want to get it reproduced. A few things would help me move this forward...”", y, BLUE, size=15)
y = callout(c, "Security: “OpenHive Security Patch — requests 2.6.0 to 2.32.3, remediating seven known CVEs including CVE-2018-18074.” A real patch PR was opened on the repo.", y, RED, size=15)
y = callout(c, "Daily Digest (a real GitHub issue): “Health score 42... merge the requests security upgrade today, but block the PR with the false coverage claims first.”", y, AMBER, size=15)
para(c, "Try it live:  openhive-omega.vercel.app   ·   backend /health, /stats, /verdicts all return real JSON",
     st(MONO, 12, MUTED, 18), MARGIN, y, CW)
c.showPage()

# ---------- Slide 8 — Market ----------
chrome(c, BLUE, 8)
y = header(c, BLUE, "The opportunity", "Every open source project is a customer")
y = bullets(c, [
    f"{b('28M+ public repositories')} on GitHub, maintained by tens of millions of people, most of them solo and unpaid.",
    f"{b('Maintainer burnout')} is the number one sustainability risk in open source, and the cause of most abandoned dependencies.",
    "Today's spend flows to contributor tooling and CI. The maintainer's own workload is almost entirely unserved.",
    f"{b('Wedge')}: solo maintainers of active public repos. {b('Expansion')}: organizations, private repos, and per-repo agent policies.",
], y, BLUE, size=17, gap=18)
callout(c, "OpenHive is itself open source under MIT, because the people who need it most are the people who built the open source world.", y - 6, BLUE)
c.showPage()

# ---------- Slide 9 — Technical differentiation ----------
chrome(c, INK, 9)
y = header(c, INK, "Under the hood", "Built like a product, not a demo")
y = bullets(c, [
    f"{b('Stack')}: FastAPI on Render, LangGraph orchestration, Claude Sonnet 4.6, GitHub Models tracing, ChromaDB shared memory, Supabase persistence, Next.js on Vercel.",
    f"{b('Auditability')}: every agent verdict is written to Supabase before any GitHub write, so nothing un-auditable ever ships.",
    f"{b('Concurrency-safe')}: per-event LangGraph state isolation and per-agent namespaced memory collections.",
    f"{b('Token discipline')}: one capped Claude call per event; the Security Agent calls Claude only when a CVE actually exists.",
    f"{b('No runaway loops')}: default-branch guards, and agents never review or triage OpenHive's own output.",
], y, AMBER, size=16, gap=15)
c.showPage()

# ---------- Slide 10 — Roadmap + team ----------
chrome(c, AMBER, 10)
y = header(c, AMBER, "What's next", "Roadmap and team")
y = bullets(c, [
    f"{b('One-click GitHub App')} install, zero configuration, OpenHive live on any repo in thirty seconds.",
    f"{b('Dashboard charts')}: repository health over time and per-agent trends.",
    f"{b('Multi-tenant')} deployments with per-repo agent policies and configurable token budgets.",
], y, AMBER, size=17, gap=16)
para(c, b("Team"), st(SANS, 16, INK, 22), MARGIN, y, CW)
y -= 30
para(c, "Suchita Yerramsetty, built end to end: backend, agents, consensus protocol, frontend, and deployment.",
     st(SANS, 16, MUTED, 23), MARGIN, y, CW)
y -= 50
callout(c, "Built for the people who built the internet and never got a team.", y, AMBER)
c.showPage()

c.save()
print("Wrote", OUT)
