"use client";

import { useEffect, useState } from "react";

const BACKEND = "https://openhive-backend.onrender.com";
const REPO = "yerramsettysuchita/openhive-test";

const AGENT_COLOR = {
  triage: "#1b5fa8",
  pr_review: "#0f7c6e",
  security: "#c23b22",
  docs: "#2e7d32",
  health: "#2e7d32",
  consensus: "#7c3aed",
  digest: "#d47c0f",
};
const AGENT_ORDER = ["triage", "pr_review", "security", "docs", "health", "consensus", "digest"];

const LABEL = {
  thriving: { fg: "#2e7d32", bg: "#e8f5e9" },
  stable: { fg: "#1b5fa8", bg: "#e4eef9" },
  slowing: { fg: "#d47c0f", bg: "#fef3cd" },
  at_risk: { fg: "#c23b22", bg: "#fde8e4" },
  unknown: { fg: "#6b6862", bg: "#efece5" },
};

// Real data from actual OpenHive runs — used as graceful fallback so the page
// is never empty or broken while the Render free tier wakes up.
const FALLBACK = {
  stats: { total_verdicts: 14, per_agent: { triage: 5, pr_review: 1, security: 1, docs: 1, health: 2, consensus: 2, digest: 2 } },
  health: {
    score: 42,
    label: "slowing",
    insight:
      "With only 2 commits from a single contributor in the last 30 days, the repository shows signs of stagnating contributor diversity and very low development velocity.",
  },
  feed: [
    { agent: "triage", classification: "bug", reason: "Results list shows stale data because it is not re-fetched or invalidated when the date filter changes.", when: "2h ago" },
    { agent: "security", classification: "critical", reason: "requests 2.6.0 carries seven known CVEs including CVE-2018-18074. A patch PR was opened upgrading to 2.32.3.", when: "3h ago" },
    { agent: "pr_review", classification: "request_changes", reason: "The PR claims complete unit test coverage and docstrings, but the diff adds zero tests and zero docstrings.", when: "3h ago" },
    { agent: "docs", classification: "add_docstrings", reason: "Two functions are missing docstrings covering parameters, return values, and edge cases.", when: "4h ago" },
    { agent: "health", classification: "slowing", reason: "Health score 42 of 100. Low development velocity and single-contributor risk.", when: "5h ago" },
    { agent: "consensus", classification: "disagreement", reason: "pr_review and health reached differing conclusions on the same pull request.", when: "3h ago" },
  ],
  disagreements: [
    { delta: 0.53, summary: "pr_review is very confident this is request_changes, while health reads it as slowing and is somewhat unsure." },
  ],
  digest: {
    preview:
      "The repository is in a rough spot today with a health score of 42 and clear signs of stagnation. Six findings came in over the last 24 hours and three of them need your attention now. Merge the requests security upgrade today, but block the PR with the false coverage claims first.",
    url: "https://github.com/yerramsettysuchita/openhive-test/issues/10",
  },
};

function summarize(raw) {
  if (!raw || typeof raw !== "object") return "";
  const keys = ["review_comment", "pr_description", "key_insight", "gap_summary", "reasoning", "recommended_action", "disagreement_summary", "digest"];
  for (const k of keys) if (raw[k]) return String(raw[k]);
  return "";
}

function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

async function getJSON(path) {
  const r = await fetch(`${BACKEND}${path}`, { signal: AbortSignal.timeout(10000) });
  if (!r.ok) throw new Error("bad status");
  return r.json();
}

export default function Home() {
  const [status, setStatus] = useState("checking"); // checking | live | waking
  const [data, setData] = useState({ ...FALLBACK });
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      let st = "waking";
      try { await getJSON("/health"); st = "live"; } catch {}

      let stats = FALLBACK.stats;
      try { const s = await getJSON("/stats"); if (s && s.total_verdicts != null) stats = s; } catch {}

      let feed = FALLBACK.feed;
      let disagreements = FALLBACK.disagreements;
      let digest = FALLBACK.digest;
      let liveInsight = null;
      try {
        const v = await getJSON(`/verdicts?repo=${encodeURIComponent(REPO)}&limit=8`);
        if (Array.isArray(v) && v.length) {
          feed = v
            .filter((r) => r.agent_name !== "digest")
            .map((r) => ({
              agent: r.agent_name,
              classification: (r.classification || r.event_type || "processed").replace(/_/g, " "),
              reason: summarize(r.raw_response) || `Processed a ${r.event_type} event.`,
              when: timeAgo(r.created_at),
            }));
          const dis = v
            .filter((r) => r.agent_name === "consensus" && r.classification === "disagreement")
            .map((r) => ({ delta: r.raw_response?.confidence_delta ?? "—", summary: r.raw_response?.disagreement_summary || "The swarm diverged on this event." }));
          if (dis.length) disagreements = dis;
          const hrow = v.find((r) => r.agent_name === "health");
          liveInsight = hrow?.raw_response?.key_insight || null;
          const drow = v.find((r) => r.agent_name === "digest");
          if (drow) digest = { preview: drow.raw_response?.digest || FALLBACK.digest.preview, url: drow.github_action_url || FALLBACK.digest.url };
        }
      } catch {}

      let health = { ...FALLBACK.health };
      try {
        const h = await getJSON(`/health/score?repo=${encodeURIComponent(REPO)}`);
        if (h && (h.score || h.label)) {
          health = { score: h.score || FALLBACK.health.score, label: h.label || "unknown", insight: liveInsight || FALLBACK.health.insight };
        } else if (liveInsight) {
          health.insight = liveInsight;
        }
      } catch { if (liveInsight) health.insight = liveInsight; }

      if (cancelled) return;
      setStatus(st);
      setData({ stats, feed, disagreements, digest, health });
      setTimeout(() => !cancelled && setProgress(Number(health.score) || 0), 200);
    }

    load();
    // animate the fallback score in immediately
    setTimeout(() => setProgress(FALLBACK.health.score), 200);
    return () => { cancelled = true; };
  }, []);

  const lbl = LABEL[data.health.label] || LABEL.unknown;
  const maxCount = Math.max(1, ...Object.values(data.stats.per_agent || {}));
  const agentsActive = AGENT_ORDER.filter((a) => ["triage", "pr_review", "security", "docs", "health"].includes(a) && (data.stats.per_agent || {})[a]).length;

  return (
    <>
      {/* Header */}
      <header className="header">
        <div className="container header-inner">
          <div className="logo-mark">🐝</div>
          <span className="wordmark">OpenHive</span>
          <span className="status">
            <span className={`pulse ${status === "live" ? "live" : ""}`} />
            {status === "live" ? "backend live" : status === "checking" ? "connecting…" : "backend waking up"}
          </span>
          <span className="header-spacer" />
          <a className="btn" href="https://github.com/yerramsettysuchita/openhive" target="_blank" rel="noreferrer">
            <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
            GitHub
          </a>
          <a className="btn btn-primary" href={`${BACKEND}/docs`} target="_blank" rel="noreferrer">API docs</a>
        </div>
      </header>

      {/* Hero */}
      <section className="container hero">
        <span className="badge"><span className="pulse live" /> Live production deployment</span>
        <h1 className="hero-title">An AI engineering team for <em>solo maintainers</em></h1>
        <p className="hero-sub">
          Five specialized agents read every issue, pull request, and dependency change, debate their findings through a transparent consensus protocol, and post what actually needs you, all where the work already lives.
        </p>
        <div className="hero-stats">
          <div className="hero-stat"><div className="num">{data.stats.total_verdicts}</div><div className="lbl">total findings</div></div>
          <div className="hero-stat"><div className="num">{agentsActive}/5</div><div className="lbl">agents active</div></div>
          <div className="hero-stat"><div className="num">{(data.stats.per_agent || {}).consensus || data.disagreements.length}</div><div className="lbl">disagreements surfaced</div></div>
          <div className="hero-stat"><div className="num">{(data.stats.per_agent || {}).digest || 1}</div><div className="lbl">daily digests</div></div>
        </div>
      </section>

      {/* Health + Agent activity */}
      <section className="container grid-2">
        <div className="card">
          <div className="card-head"><span className="card-title">Repository health</span></div>
          <div className="health-score">
            <span className="health-num" style={{ color: lbl.fg }}>{data.health.score}</span>
            <span className="health-out">/ 100</span>
          </div>
          <span className="label-pill" style={{ color: lbl.fg, background: lbl.bg }}>{String(data.health.label).replace("_", " ")}</span>
          <div className="progress"><div className="progress-fill" style={{ width: `${progress}%`, background: lbl.fg }} /></div>
          <p className="insight">{data.health.insight}</p>
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Agent activity</span></div>
          <div className="bars">
            {AGENT_ORDER.filter((a) => (data.stats.per_agent || {})[a]).map((a) => (
              <div className="bar-row" key={a}>
                <span className="bar-name">{a}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${((data.stats.per_agent[a]) / maxCount) * 100}%`, background: AGENT_COLOR[a] || "#888" }} />
                </div>
                <span className="bar-count">{data.stats.per_agent[a]}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Recent agent actions */}
      <section className="container">
        <div className="card">
          <div className="card-head">
            <span className="card-title">Recent agent actions</span>
            <button className="btn" onClick={() => window.location.reload()}>Refresh</button>
          </div>
          {data.feed.map((f, i) => (
            <div className="feed-item" key={i}>
              <div><span className={`pill p-${f.agent}`}>{f.agent}</span></div>
              <div>
                <div className="feed-cls">{f.classification}</div>
                <div className="feed-reason">{f.reason}</div>
              </div>
              <div className="feed-time">{f.when}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Disagreement log + Digest */}
      <section className="container grid-2" style={{ marginTop: 22 }}>
        <div className="card">
          <div className="card-head"><span className="card-title">Disagreement log</span></div>
          {data.disagreements.map((d, i) => (
            <div className="disagree-item" key={i}>
              <span className="delta-badge">confidence delta {d.delta}</span>
              <div className="disagree-txt">{d.summary}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Daily digest archive</span></div>
          <p className="digest-preview">{data.digest.preview}</p>
          <a className="digest-link" href={data.digest.url} target="_blank" rel="noreferrer">View on GitHub →</a>
        </div>
      </section>

      {/* Footer */}
      <footer className="container footer">
        <span className="footer-tag">A swarm that thinks. A protocol that argues. A digest that decides.</span>
        <div className="footer-links">
          <a href={`${BACKEND}/health`} target="_blank" rel="noreferrer">/health</a>
          <a href={`${BACKEND}/stats`} target="_blank" rel="noreferrer">/stats</a>
          <a href="https://github.com/yerramsettysuchita/openhive" target="_blank" rel="noreferrer">source</a>
        </div>
      </footer>
    </>
  );
}
