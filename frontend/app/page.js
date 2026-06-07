"use client";

import { useEffect, useState } from "react";

const BACKEND = "https://openhive-backend.onrender.com";
const DEFAULT_REPO = "yerramsettysuchita/openhive-test";
const CORE = ["triage", "pr_review", "security", "docs", "health"];

const AGENT_COLOR = {
  triage: "#1b5fa8", pr_review: "#0f7c6e", security: "#c23b22",
  docs: "#2e7d32", health: "#2e7d32", consensus: "#7c3aed", digest: "#d47c0f",
};
const AGENT_ORDER = ["triage", "pr_review", "security", "docs", "health", "consensus", "digest"];
const LABEL = {
  thriving: { fg: "#2e7d32", bg: "#e8f5e9" },
  stable: { fg: "#1b5fa8", bg: "#e4eef9" },
  slowing: { fg: "#d47c0f", bg: "#fef3cd" },
  at_risk: { fg: "#c23b22", bg: "#fde8e4" },
  unknown: { fg: "#6b6862", bg: "#efece5" },
};

function summarize(raw) {
  if (!raw || typeof raw !== "object") return "";
  const keys = ["review_comment", "pr_description", "key_insight", "gap_summary", "reasoning", "recommended_action", "disagreement_summary", "digest"];
  for (const k of keys) if (raw[k]) return String(raw[k]);
  return "";
}
function timeAgo(iso) {
  if (!iso) return "no activity";
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

function makeFallback() {
  const iso = (h) => new Date(Date.now() - h * 3600000).toISOString();
  return {
    empty: false,
    stats: { total: 14, perAgent: { triage: 5, pr_review: 1, security: 1, docs: 1, health: 2, consensus: 2, digest: 2 } },
    health: { score: 42, label: "slowing", insight: "With only 2 commits from a single contributor in the last 30 days, the repository shows stagnating contributor diversity and low development velocity." },
    feed: [
      { agent: "triage", classification: "bug", reason: "Results list shows stale data because it is not re-fetched when the date filter changes.", when: "2h ago", url: "https://github.com/yerramsettysuchita/openhive-test/issues/9" },
      { agent: "security", classification: "critical", reason: "requests 2.6.0 carries seven known CVEs including CVE-2018-18074. A patch PR was opened upgrading to 2.32.3.", when: "3h ago", url: "https://github.com/yerramsettysuchita/openhive-test/pull/4" },
      { agent: "pr_review", classification: "request changes", reason: "The PR claims complete unit test coverage and docstrings, but the diff adds zero of each.", when: "3h ago", url: "https://github.com/yerramsettysuchita/openhive-test/pull/3" },
      { agent: "docs", classification: "add docstrings", reason: "Two functions are missing docstrings covering parameters, returns, and edge cases.", when: "4h ago", url: "https://github.com/yerramsettysuchita/openhive-test" },
      { agent: "health", classification: "slowing", reason: "Health score 42 of 100. Low development velocity and single-contributor risk.", when: "5h ago", url: "https://github.com/yerramsettysuchita/openhive-test/issues/5" },
      { agent: "consensus", classification: "disagreement", reason: "pr_review and health reached differing conclusions on the same pull request.", when: "3h ago", url: "https://github.com/yerramsettysuchita/openhive-test/issues/6" },
    ],
    disagreements: [{ delta: 0.53, summary: "pr_review is very confident this is request_changes, while health reads it as slowing and is somewhat unsure." }],
    digest: { preview: "The repository is in a rough spot today with a health score of 42 and clear signs of stagnation. Six findings came in over the last 24 hours and three of them need your attention now. Merge the requests security upgrade today, but block the PR with the false coverage claims first.", url: "https://github.com/yerramsettysuchita/openhive-test/issues/10" },
    swarm: { triage: { active: true, last_seen: iso(2) }, pr_review: { active: true, last_seen: iso(3) }, security: { active: true, last_seen: iso(3) }, docs: { active: true, last_seen: iso(4) }, health: { active: true, last_seen: iso(5) } },
  };
}

function emptyState() {
  const off = {};
  CORE.forEach((a) => (off[a] = { active: false, last_seen: null }));
  return {
    empty: true,
    stats: { total: 0, perAgent: {} },
    health: { score: 0, label: "unknown", insight: "No OpenHive activity has been recorded for this repository yet." },
    feed: [], disagreements: [], digest: null, swarm: off,
  };
}

function buildFromVerdicts(v) {
  const feed = v.filter((r) => r.agent_name !== "digest").slice(0, 8).map((r) => ({
    agent: r.agent_name,
    classification: (r.classification || r.event_type || "processed").replace(/_/g, " "),
    reason: summarize(r.raw_response) || `Processed a ${r.event_type} event.`,
    when: timeAgo(r.created_at),
    url: r.github_action_url || null,
  }));
  const perAgent = {};
  v.forEach((r) => (perAgent[r.agent_name] = (perAgent[r.agent_name] || 0) + 1));
  const disagreements = v
    .filter((r) => r.agent_name === "consensus" && r.classification === "disagreement")
    .map((r) => ({ delta: r.raw_response?.confidence_delta ?? "—", summary: r.raw_response?.disagreement_summary || "The swarm diverged on this event." }));
  const drow = v.find((r) => r.agent_name === "digest");
  const digest = drow ? { preview: drow.raw_response?.digest || "", url: drow.github_action_url || null } : null;
  const hrow = v.find((r) => r.agent_name === "health");
  const health = {
    score: hrow?.raw_response?.health_score ?? 0,
    label: hrow?.classification || "unknown",
    insight: hrow?.raw_response?.key_insight || "Live repository health from the OpenHive Health Agent.",
  };
  const swarm = {};
  CORE.forEach((a) => {
    const av = v.filter((r) => r.agent_name === a);
    swarm[a] = av.length ? { active: true, last_seen: av[0].created_at } : { active: false, last_seen: null };
  });
  return { empty: false, feed, disagreements, digest, health, stats: { total: v.length, perAgent }, swarm };
}

const Chevron = () => (
  <svg className="chevron" width="7" height="12" viewBox="0 0 7 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M1 1l5 5-5 5" /></svg>
);

export default function Home() {
  const [repo, setRepo] = useState(DEFAULT_REPO);
  const [repoInput, setRepoInput] = useState(DEFAULT_REPO);
  const [analyzing, setAnalyzing] = useState(false);
  const [status, setStatus] = useState("checking");
  const [data, setData] = useState(makeFallback());
  const [progress, setProgress] = useState(0);
  const [coldSeconds, setColdSeconds] = useState(0);

  async function analyse(targetRepo, allowFallback) {
    const t = (targetRepo || "").trim();
    if (!t) return;
    setAnalyzing(true);
    let st = "waking";
    try { await getJSON("/health"); st = "live"; } catch {}
    setStatus(st);

    let next;
    try {
      const v = await getJSON(`/verdicts?repo=${encodeURIComponent(t)}&limit=100`);
      if (Array.isArray(v) && v.length) next = buildFromVerdicts(v);
      else next = allowFallback ? makeFallback() : emptyState();
    } catch {
      next = allowFallback ? makeFallback() : emptyState();
    }

    if (!next.empty) {
      try {
        const h = await getJSON(`/health/score?repo=${encodeURIComponent(t)}`);
        if (h && (h.score || h.label)) next.health = { score: h.score || next.health.score, label: h.label || "unknown", insight: next.health.insight };
      } catch {}
      try {
        const s = await getJSON(`/swarm/status?repo=${encodeURIComponent(t)}`);
        if (s && Object.keys(s).length) next.swarm = s;
      } catch {}
    }

    setData(next);
    setRepo(t);
    setAnalyzing(false);
    setProgress(0);
    setTimeout(() => setProgress(Number(next.health.score) || 0), 200);
  }

  useEffect(() => {
    analyse(DEFAULT_REPO, true);
    setTimeout(() => setProgress(makeFallback().health.score), 250);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cold-start banner: while the backend is waking, count up and keep polling
  // /health until it responds, then hide the banner.
  useEffect(() => {
    if (status === "live") { setColdSeconds(0); return; }
    if (status === "checking") return;
    const tick = setInterval(() => setColdSeconds((s) => s + 1), 1000);
    const poll = setInterval(() => {
      getJSON("/health").then(() => setStatus("live")).catch(() => {});
    }, 5000);
    return () => { clearInterval(tick); clearInterval(poll); };
  }, [status]);

  const d = data;
  const lbl = LABEL[d.health.label] || LABEL.unknown;
  const perAgent = d.stats.perAgent || {};
  const maxCount = Math.max(1, ...Object.values(perAgent));
  const agentsActive = CORE.filter((a) => perAgent[a]).length;

  return (
    <>
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
            <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" /></svg>
            GitHub
          </a>
          <a className="btn btn-primary" href={`${BACKEND}/docs`} target="_blank" rel="noreferrer">API docs</a>
        </div>
      </header>

      {status === "waking" && (
        <div style={{ background: "#FFFBF0", borderBottom: "1px solid rgba(212,124,15,0.2)", padding: "10px 32px", fontSize: 12, color: "#D47C0F", fontFamily: "'Lora', serif", textAlign: "center" }}>
          The backend is waking from sleep. First response may take up to 60 seconds on the free tier. This is normal.
          <span style={{ fontWeight: 600, marginLeft: 8 }}>{coldSeconds}s</span>
        </div>
      )}

      <section className="container hero">
        <span className="badge"><span className="pulse live" /> Live production deployment</span>
        <h1 className="hero-title">An AI engineering team for <em>solo maintainers</em></h1>
        <p className="hero-sub">
          Five specialized agents read every issue, pull request, and dependency change, debate their findings through a transparent consensus protocol, and post what actually needs you, all where the work already lives.
        </p>

        <div className="repo-row">
          <input
            className="repo-input"
            value={repoInput}
            onChange={(e) => setRepoInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && analyse(repoInput, false)}
            placeholder="owner/repository-name"
            spellCheck={false}
          />
          <button className="btn btn-primary repo-btn" onClick={() => analyse(repoInput, false)} disabled={analyzing}>
            {analyzing ? "Analysing…" : "Analyse repository"}
          </button>
        </div>

        <div className="hero-stats">
          <div className="hero-stat"><div className="num">{d.stats.total}</div><div className="lbl">total findings</div></div>
          <div className="hero-stat"><div className="num">{agentsActive}/5</div><div className="lbl">agents active</div></div>
          <div className="hero-stat"><div className="num">{perAgent.consensus || d.disagreements.length}</div><div className="lbl">disagreements surfaced</div></div>
          <div className="hero-stat"><div className="num">{perAgent.digest || (d.digest ? 1 : 0)}</div><div className="lbl">daily digests</div></div>
        </div>
      </section>

      <section className="container">
        {d.empty && (
          <div className="repo-empty">
            <strong>{repo}</strong> has not been monitored by OpenHive yet.{" "}
            <a href="https://github.com/yerramsettysuchita/openhive#-install-openhive-on-your-repo-under-5-minutes" target="_blank" rel="noreferrer">See the installation guide →</a>
          </div>
        )}

        <div className="swarm-strip">
          <span className="swarm-label">Swarm status</span>
          <div className="swarm-items">
            {CORE.map((a) => {
              const s = d.swarm[a] || {};
              const recent = s.last_seen && (Date.now() - new Date(s.last_seen).getTime()) / 3600000 < 24;
              return (
                <div className="swarm-item" key={a}>
                  <div className="top"><span className={`swarm-dot ${recent ? "on" : "off"}`} /><span className="swarm-name">{a}</span></div>
                  <span className="swarm-time">{timeAgo(s.last_seen)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="container grid-2">
        <div className="card">
          <div className="card-head"><span className="card-title">Repository health</span></div>
          <div className="health-score">
            <span className="health-num" style={{ color: lbl.fg }}>{d.health.score}</span>
            <span className="health-out">/ 100</span>
          </div>
          <span className="label-pill" style={{ color: lbl.fg, background: lbl.bg }}>{String(d.health.label).replace("_", " ")}</span>
          <div className="progress"><div className="progress-fill" style={{ width: `${progress}%`, background: lbl.fg }} /></div>
          <p className="insight">{d.health.insight}</p>
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Agent activity</span></div>
          <div className="bars">
            {AGENT_ORDER.filter((a) => perAgent[a]).map((a) => (
              <div className="bar-row" key={a}>
                <span className="bar-name">{a}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${(perAgent[a] / maxCount) * 100}%`, background: AGENT_COLOR[a] || "#888" }} /></div>
                <span className="bar-count">{perAgent[a]}</span>
              </div>
            ))}
            {Object.keys(perAgent).length === 0 && <div className="empty">No agent activity yet.</div>}
          </div>
        </div>
      </section>

      <section className="container">
        <div className="card">
          <div className="card-head">
            <span className="card-title">Recent agent actions</span>
            <button className="btn" onClick={() => analyse(repo, false)} disabled={analyzing}>{analyzing ? "Refreshing…" : "Refresh"}</button>
          </div>
          {d.feed.length === 0 && <div className="empty">No agent findings for this repository yet.</div>}
          {d.feed.map((f, i) => {
            const href = f.url || `https://github.com/${repo}`;
            return (
              <a className="feed-link" href={href} target="_blank" rel="noreferrer" key={i}>
                <div className="feed-item feed-row3">
                  <div><span className={`pill p-${f.agent}`}>{f.agent}</span></div>
                  <div>
                    <div className="feed-cls">{f.classification}</div>
                    <div className="feed-reason">{f.reason}</div>
                  </div>
                  <div className="feed-time">{f.when}</div>
                  <Chevron />
                </div>
              </a>
            );
          })}
        </div>
      </section>

      <section className="container grid-2" style={{ marginTop: 22 }}>
        <div className="card">
          <div className="card-head"><span className="card-title">Disagreement log</span></div>
          {d.disagreements.length === 0 && <div className="empty">No disagreements surfaced for this repository.</div>}
          {d.disagreements.map((x, i) => (
            <div className="disagree-item" key={i}>
              <span className="delta-badge">confidence delta {x.delta}</span>
              <div className="disagree-txt">{x.summary}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="card-head"><span className="card-title">Daily digest archive</span></div>
          {d.digest ? (
            <>
              <p className="digest-preview">{d.digest.preview}</p>
              {d.digest.url && <a className="digest-link" href={d.digest.url} target="_blank" rel="noreferrer">View on GitHub →</a>}
            </>
          ) : (
            <div className="empty">No digest posted for this repository yet.</div>
          )}
        </div>
      </section>

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
