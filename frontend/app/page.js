"use client";

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

const AGENTS = ["triage", "pr_review", "security", "docs", "health"];

const LABEL_COLORS = {
  thriving: { bg: "#143a2a", fg: "#3fb950" },
  stable: { bg: "#1f3a5f", fg: "#58a6ff" },
  slowing: { bg: "#4a3a13", fg: "#ffcf4d" },
  at_risk: { bg: "#4a1f22", fg: "#f85149" },
};

function summarize(raw) {
  if (!raw || typeof raw !== "object") return "";
  const keys = [
    "review_comment", "pr_description", "key_insight", "gap_summary",
    "reasoning", "recommended_action", "disagreement_summary", "digest",
  ];
  for (const k of keys) if (raw[k]) return String(raw[k]);
  return "";
}

function timeAgo(iso) {
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function Home() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!SUPABASE_URL || !SUPABASE_KEY) {
      setError("missing-env");
      return;
    }
    const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
    supabase
      .from("agent_verdicts")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(100)
      .then(({ data, error }) => {
        if (error) setError(error.message);
        else setRows(data || []);
      });
  }, []);

  if (error === "missing-env") {
    return (
      <div className="wrap">
        <Header live={false} />
        <div className="notice">
          Set <code>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
          <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in your Vercel environment
          variables to connect the dashboard to your OpenHive data.
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wrap">
        <Header live={false} />
        <div className="notice">Could not load data: {error}</div>
      </div>
    );
  }

  if (rows === null) {
    return (
      <div className="wrap">
        <Header live={false} />
        <div className="spin">Loading the swarm…</div>
      </div>
    );
  }

  const healthRow = rows.find((r) => r.agent_name === "health");
  const score = healthRow?.raw_response?.health_score ?? null;
  const label = healthRow?.classification ?? "unknown";
  const labelColor = LABEL_COLORS[label] || { bg: "#1c2330", fg: "#8b949e" };

  const agentRows = rows.filter((r) => AGENTS.includes(r.agent_name));
  const disagreements = rows.filter(
    (r) => r.agent_name === "consensus" && r.classification === "disagreement"
  );
  const digests = rows.filter((r) => r.agent_name === "digest");
  const activeAgents = new Set(agentRows.map((r) => r.agent_name)).size;

  return (
    <div className="wrap">
      <Header live={true} />

      <div className="hero">
        <div className="score-card">
          <div className="score-num" style={{ color: labelColor.fg }}>
            {score ?? "—"}
          </div>
          <div className="score-out">out of 100</div>
          <div
            className="score-label"
            style={{ background: labelColor.bg, color: labelColor.fg }}
          >
            {label.replace("_", " ")}
          </div>
        </div>
        <div className="hero-copy">
          <h2>Repository health, watched continuously</h2>
          <p>
            <span className="tag">A swarm that thinks. A protocol that argues.
            A digest that decides.</span>{" "}
            Five AI agents read every issue, pull request, and dependency change,
            debate their findings through a transparent consensus protocol, and
            surface what actually needs you.
          </p>
        </div>
      </div>

      <div className="stats">
        <Stat n={rows.length} l="Total findings" />
        <Stat n={`${activeAgents}/5`} l="Agents active" />
        <Stat n={disagreements.length} l="Disagreements surfaced" />
        <Stat n={digests.length} l="Daily digests" />
      </div>

      <div className="cols">
        <div className="panel">
          <h3>🐝 Agent activity feed</h3>
          <div className="feed">
            {agentRows.length === 0 && <div className="empty">No agent findings yet.</div>}
            {agentRows.map((r) => (
              <div className="item" key={r.id}>
                <div className="row">
                  <span className={`badge b-${r.agent_name}`}>{r.agent_name}</span>
                  <span className="cls">{r.classification || r.event_type}</span>
                  <span className="when">{timeAgo(r.created_at)}</span>
                </div>
                <div className="summary">
                  {summarize(r.raw_response) || `Processed a ${r.event_type} event.`}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <h3>⚖️ Disagreement log</h3>
          <div className="feed">
            {disagreements.length === 0 && (
              <div className="empty">
                No disagreements yet. When two agents diverge by more than 0.3
                confidence, the conflict shows up here.
              </div>
            )}
            {disagreements.map((r) => (
              <div className="disagreement" key={r.id}>
                <div className="delta">
                  confidence delta {r.raw_response?.confidence_delta ?? "—"} ·{" "}
                  {timeAgo(r.created_at)}
                </div>
                <div className="txt">
                  {r.raw_response?.disagreement_summary ||
                    "The swarm reached differing conclusions on this event."}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="section-title">📜 Daily digest archive</div>
      <div className="section-sub">
        The interface is the digest — one plain-language morning note, ranked by
        what matters.
      </div>
      {digests.length === 0 && (
        <div className="empty">No digests posted yet.</div>
      )}
      {digests.map((r) => (
        <div className="digest-card" key={r.id}>
          <div className="meta">
            <span>{new Date(r.created_at).toLocaleString()}</span>
            {r.github_action_url && <a href={r.github_action_url} target="_blank" rel="noreferrer">view on GitHub →</a>}
          </div>
          <div className="body">{r.raw_response?.digest || "(digest text unavailable)"}</div>
        </div>
      ))}

      <div className="footer">
        OpenHive · built for the people who built the internet and never got a team.
      </div>
    </div>
  );
}

function Header({ live }) {
  return (
    <div className="nav">
      <div className="brand">
        <span className="logo">🐝</span>
        <div>
          <h1>OpenHive</h1>
          <p>An AI engineering team for solo maintainers</p>
        </div>
      </div>
      <div className="nav-links">
        <span>
          <span className={`dot ${live ? "live" : "off"}`} />
          {live ? "Backend live" : "Connecting"}
        </span>
        {BACKEND_URL && <a href={`${BACKEND_URL}/health`} target="_blank" rel="noreferrer">API</a>}
        <a href="https://github.com/yerramsettysuchita/openhive" target="_blank" rel="noreferrer">GitHub</a>
      </div>
    </div>
  );
}

function Stat({ n, l }) {
  return (
    <div className="stat">
      <div className="n">{n}</div>
      <div className="l">{l}</div>
    </div>
  );
}
