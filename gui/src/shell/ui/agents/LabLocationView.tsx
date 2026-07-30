import type { Agent } from "@core/agent/Agent";
import { connectedDurationMs, formatDuration } from "@core/agent/Agent";
import { APP_ROUTE, LOAD_REE_PARAM } from "@core/app-shell/pages";
import { useAgents } from "@shell/data/agents/agents";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Ic } from "../shared/components/Icon";
import { C, F } from "../theme/theme";

interface LabLocationViewProps {
  onBack: () => void;
}

// Step 1 of REE creation: choose which agent (lab location) will host the
// workbench. Selecting one carries its id into the workbench/image step, which
// pins the REE to that agent on provision.
export function LabLocationView({ onBack }: LabLocationViewProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { data: agents, isLoading, isError, error } = useAgents();

  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const chooseAgent = (agent: Agent) => {
    // "Load an existing REE" is chosen on the landing screen and asked for on
    // the workbench step, so the intent rides along through this one.
    const params = new URLSearchParams({ agentId: agent.id });
    if (searchParams.get(LOAD_REE_PARAM)) params.set(LOAD_REE_PARAM, "1");
    navigate(`${APP_ROUTE.WORKSPACE}?${params.toString()}`);
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: 24, fontFamily: F.sans }}>
      <div style={{ maxWidth: 620, margin: "0 auto", animation: "fadeUp 0.4s ease" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
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
        </div>

        <div style={{ marginBottom: 18 }}>
          <h1
            style={{ fontSize: 22, fontWeight: 600, color: C.text, letterSpacing: -0.4, margin: 0 }}
          >
            Choose a lab location
          </h1>
          <p style={{ fontSize: 13, color: C.textMuted, margin: "4px 0 0", lineHeight: 1.6 }}>
            Pick the agent that will host this REE's workbench. The REE stays pinned to it.
          </p>
        </div>

        {isLoading ? (
          <Notice text="Loading agents…" />
        ) : isError ? (
          <Notice
            text={`Failed to load agents: ${error instanceof Error ? error.message : "unknown error"}`}
            tone="error"
          />
        ) : !agents || agents.length === 0 ? (
          <EmptyState />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {agents.map((agent) => (
              <AgentChoice
                key={agent.id}
                agent={agent}
                nowMs={nowMs}
                onSelect={() => chooseAgent(agent)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AgentChoice({
  agent,
  nowMs,
  onSelect,
}: {
  agent: Agent;
  nowMs: number;
  onSelect: () => void;
}) {
  const uptime = formatDuration(connectedDurationMs(agent, nowMs));
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 14,
        width: "100%",
        textAlign: "left",
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "14px 16px",
        cursor: "pointer",
        boxShadow: "0 1px 6px rgba(0,0,0,0.04)",
        fontFamily: F.sans,
      }}
    >
      <span
        style={{
          width: 38,
          height: 38,
          borderRadius: 10,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: C.accentBg,
          border: `1px solid ${C.accentBorder}`,
          color: C.accent,
        }}
      >
        {Ic.cpu(18)}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: C.text }}>
          {agent.hostname || agent.id}
        </div>
        <div style={{ fontSize: 12, color: C.textMuted, fontFamily: F.mono, marginTop: 2 }}>
          {agent.dockerMode || "—"} · {agent.version || "—"} · up {uptime}
        </div>
      </div>
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          color: C.done,
          fontSize: 12,
          flexShrink: 0,
        }}
      >
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: C.done }} />
        connected
      </span>
      <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>{Ic.chevR(16)}</span>
    </button>
  );
}

function Notice({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "18px 18px",
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
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        padding: "32px 18px",
        textAlign: "center",
      }}
    >
      <div
        style={{ color: C.textMuted, display: "flex", justifyContent: "center", marginBottom: 10 }}
      >
        {Ic.cpu(24)}
      </div>
      <div style={{ fontSize: 14, fontWeight: 500, color: C.textMid, marginBottom: 4 }}>
        No agents connected
      </div>
      <div style={{ fontSize: 12, color: C.textMuted, lineHeight: 1.6 }}>
        A workbench needs an agent to host it. Start one pointing at this control plane:
        <br />
        <code style={{ fontFamily: F.mono, color: C.textMid }}>
          WORKBENCH_API_WS_URL=ws://…/agent/connect python -m repo2ree_agent
        </code>
      </div>
    </div>
  );
}
