# OpenHive — 3-minute demo video script

Target length 3:00. Record at 1080p (or 720p minimum). Use screen recording with
voiceover. Keep the cursor calm. Have these tabs open before you start:

1. The README at github.com/yerramsettysuchita/openhive
2. The dashboard at https://openhive-omega.vercel.app
3. The openhive-test repo Issues tab
4. The security patch PR (openhive-test, PR #4)
5. The daily digest issue (openhive-test, issue #10)

Before recording: open the dashboard once to wake the Render backend (free tier
cold start ~50s) so it shows "backend live" green during the take.

---

## 0:00 – 0:18  |  The hook
**On screen:** the README top (manifesto block) or the dashboard hero.
**Say:**
> Open source runs the world, and almost every piece of it is maintained by one
> unpaid person doing the work of ten. They triage issues, review pull requests,
> chase security holes, and write docs, alone. OpenHive gives that person a team.

## 0:18 – 0:38  |  What it is
**On screen:** scroll the dashboard hero and the five-agent section / README agents table.
**Say:**
> OpenHive is a swarm of five AI agents that installs into any GitHub repo with a
> single Action. Triage, PR Review, Security, Docs, and Health. They wake on every
> event, reason with Claude, share memory, and act, all inside GitHub.

## 0:38 – 1:30  |  LIVE: a real event, end to end
**On screen:** go to openhive-test → Issues → New issue. Title it something like
"Search returns stale results after changing the filter." Submit it. Then switch to
the issue page and wait. Within about a minute the Triage Agent comment appears.
**Say (while it processes):**
> Let me show you live. I am opening a real issue on a real repository right now.
> GitHub sends the event to the OpenHive backend on Render. The Triage Agent reads
> it, classifies it, and writes back, no human in the loop.
**When the comment appears, scroll to it and read the key part:**
> There it is. It correctly called this a bug, asked the exact clarifying questions
> a senior engineer would ask, and look at the end of the comment.

## 1:30 – 1:58  |  The differentiator: transparent disagreement
**On screen:** highlight the disagreement note at the bottom of the Triage comment.
**Say:**
> This line is what makes OpenHive different. When the agents do not agree, OpenHive
> says so, out loud, in the comment itself. Here it is telling the maintainer that
> the Health Agent reads this repository differently, so weigh both views before
> acting. Most agent systems hide their internal conflict. OpenHive surfaces it.

## 1:58 – 2:22  |  Security agent opens a real patch PR
**On screen:** open PR #4 (OpenHive Security Patch). Show the title and the body listing CVEs.
**Say:**
> The Security Agent does not just flag problems. When it found that requests 2.6.0
> had seven known CVEs, it opened this patch PR automatically, upgrading to a safe
> version, with every CVE explained. A fix, not just an alert.

## 2:22 – 2:42  |  The daily digest + dashboard
**On screen:** open digest issue #10, then switch to the dashboard showing health 42,
the agent activity bars, and the disagreement log.
**Say:**
> Every day the swarm posts one plain-English digest, ranked by what matters. And
> the dashboard shows it all live: the health score, every agent's activity, and the
> full disagreement log, pulled straight from the production backend.

## 2:42 – 3:00  |  Close
**On screen:** dashboard hero or README, then the three live links.
**Say:**
> Five agents. A protocol that argues in the open. A digest that decides. Live right
> now, open source under MIT, and built for the people who built the internet and
> never got a team. This is OpenHive.

---

### Tips
- If the Triage comment is slow (cold start), keep narrating the architecture; it
  will land. You can also pre-open one earlier issue to show a ready comment as backup.
- Show the green "backend live" dot in the dashboard header at least once.
- Export as MP4 (H.264). Upload unlisted to YouTube or attach directly per the rules.
