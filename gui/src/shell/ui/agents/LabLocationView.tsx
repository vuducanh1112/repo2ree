import type { Agent } from "@core/agent/Agent";
import { connectedDurationMs, formatDuration } from "@core/agent/Agent";
import { APP_ROUTE, LOAD_REE_PARAM } from "@core/app-shell/pages";
import { useAgents } from "@shell/data/agents/agents";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Ic } from "../shared/components/Icon";
import styles from "./LabLocationView.module.css";

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
    <div className={styles.screen}>
      <div className={styles.column}>
        <div className={styles.backRow}>
          <button type="button" onClick={onBack} className={styles.back}>
            {Ic.arrowLeft(15)} Back
          </button>
        </div>

        <div className={styles.heading}>
          <h1 className={styles.title}>Choose a lab location</h1>
          <p className={styles.subtitle}>
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
          <div className={styles.choices}>
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
    <button type="button" onClick={onSelect} className={styles.choice}>
      <span aria-hidden className={styles.choiceIcon}>
        {Ic.cpu(18)}
      </span>
      <div className={styles.choiceBody}>
        <div className={styles.choiceName}>{agent.hostname || agent.id}</div>
        <div className={styles.choiceMeta}>
          {agent.dockerMode || "—"} · {agent.version || "—"} · up {uptime}
        </div>
      </div>
      <span className={styles.connected}>
        <span aria-hidden className={styles.connectedDot} />
        connected
      </span>
      <span aria-hidden className={styles.chevron}>
        {Ic.chevR(16)}
      </span>
    </button>
  );
}

function Notice({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div className={styles.notice} data-tone={tone}>
      {text}
    </div>
  );
}

function EmptyState() {
  return (
    <div className={styles.empty}>
      <div aria-hidden className={styles.emptyIcon}>
        {Ic.cpu(24)}
      </div>
      <div className={styles.emptyTitle}>No agents connected</div>
      <div className={styles.emptyHint}>
        A workbench needs an agent to host it. Start one pointing at this control plane:
        <br />
        <code>WORKBENCH_API_WS_URL=ws://…/agent/connect python -m repo2ree_agent</code>
      </div>
    </div>
  );
}
