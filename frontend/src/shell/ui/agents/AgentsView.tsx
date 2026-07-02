import type { Agent } from "@core/agent/Agent";
import { connectedDurationMs, formatDuration } from "@core/agent/Agent";
import { useAgents } from "@shell/data/agents/agents";
import type React from "react";
import { useEffect, useState } from "react";
import { Ic } from "../shared/components/Icon";
import { C, F } from "../theme/theme";

interface AgentsViewProps {
  onBack: () => void;
}

const COLS = "1.4fr 1fr 0.8fr 0.8fr 0.9fr" as const;

export function AgentsView({ onBack }: AgentsViewProps) {
  const { data: agents, isLoading, isError, error, refetch, isFetching } = useAgents();

  // Tick a wall clock so the "connected for" column counts up live; the pure
  // duration helpers read it. One interval for the whole table.
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: 24, fontFamily: F.sans }}>
      <div style={{ maxWidth: 860, margin: "0 auto", animation: "fadeUp 0.4s ease" }}>
        <Header onBack={onBack} onRefresh={() => void refetch()} isFetching={isFetching} />

        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 14,
            boxShadow: "0 2px 12px rgba(0,0,0,0.05)",
            overflow: "hidden",
          }}
        >
          <HeaderRow />
          {isLoading ? (
            <StatusRow text="Loading agents…" />
          ) : isError ? (
            <StatusRow
              text={`Failed to load agents: ${error instanceof Error ? error.message : "unknown error"}`}
              tone="error"
            />
          ) : !agents || agents.length === 0 ? (
            <EmptyState />
          ) : (
            agents.map((agent) => <AgentRow key={agent.id} agent={agent} nowMs={nowMs} />)
          )}
        </div>
      </div>
    </div>
  );
}

function Header({
  onBack,
  onRefresh,
  isFetching,
}: {
  onBack: () => void;
  onRefresh: () => void;
  isFetching: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
      <button
        type="button"
        onClick={onBack}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "7px 12px",
          color: C.textMid,
          fontSize: 13,
          cursor: "pointer",
        }}
      >
        {Ic.arrowLeft(15)} Back
      </button>
      <div style={{ flex: 1 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 600, color: C.text, letterSpacing: -0.4, margin: 0 }}
        >
          Workbench Agents
        </h1>
        <p style={{ fontSize: 13, color: C.textMuted, margin: "2px 0 0" }}>
          Runners currently dialed into this control plane
        </p>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        title="Refresh"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "7px 12px",
          color: C.textMid,
          fontSize: 13,
          cursor: "pointer",
          opacity: isFetching ? 0.6 : 1,
        }}
      >
        {Ic.refresh(15)} Refresh
      </button>
    </div>
  );
}

function HeaderRow() {
  const cell: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    color: C.textMuted,
  };
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: COLS,
        gap: 12,
        padding: "12px 18px",
        borderBottom: `1px solid ${C.border}`,
        background: C.surfaceAlt,
      }}
    >
      <div style={cell}>Host</div>
      <div style={cell}>Agent ID</div>
      <div style={cell}>Runtime</div>
      <div style={cell}>Version</div>
      <div style={cell}>Connected</div>
    </div>
  );
}

function AgentRow({ agent, nowMs }: { agent: Agent; nowMs: number }) {
  const uptime = formatDuration(connectedDurationMs(agent, nowMs));
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: COLS,
        gap: 12,
        padding: "14px 18px",
        borderBottom: `1px solid ${C.border}`,
        alignItems: "center",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <span style={{ color: C.done, display: "flex" }} title="Connected">
          {Ic.cpu(15)}
        </span>
        <span
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: C.text,
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {agent.hostname || "—"}
        </span>
      </div>
      <div
        style={{
          fontSize: 12,
          color: C.textMid,
          fontFamily: F.mono,
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {agent.id}
      </div>
      <div style={{ fontSize: 12, color: C.textMid }}>{agent.dockerMode || "—"}</div>
      <div style={{ fontSize: 12, color: C.textMid, fontFamily: F.mono }}>
        {agent.version || "—"}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: C.done }} />
        <span style={{ fontSize: 12, color: C.textMid }}>{uptime}</span>
      </div>
    </div>
  );
}

function StatusRow({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div
      style={{
        padding: "20px 18px",
        fontSize: 13,
        color: tone === "error" ? C.error : C.textMuted,
      }}
    >
      {text}
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ padding: "32px 18px", textAlign: "center" }}>
      <div
        style={{ color: C.textMuted, display: "flex", justifyContent: "center", marginBottom: 10 }}
      >
        {Ic.cpu(24)}
      </div>
      <div style={{ fontSize: 14, fontWeight: 500, color: C.textMid, marginBottom: 4 }}>
        No agents connected
      </div>
      <div style={{ fontSize: 12, color: C.textMuted, lineHeight: 1.6 }}>
        Start one pointing at this control plane:
        <br />
        <code style={{ fontFamily: F.mono, color: C.textMid }}>
          WORKBENCH_API_WS_URL=ws://…/agent/connect python -m repo2ree_agent
        </code>
      </div>
    </div>
  );
}
