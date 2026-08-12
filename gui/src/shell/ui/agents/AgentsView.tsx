import type { Agent } from "@core/agent/Agent";
import { connectedDurationMs, formatDuration } from "@core/agent/Agent";
import { useAgents } from "@shell/data/agents/agents";
import { useEffect, useState } from "react";
import { Ic } from "../shared/components/Icon";
import styles from "./AgentsView.module.css";

interface AgentsViewProps {
  onBack: () => void;
}

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
    <div className={styles.screen}>
      <div className={styles.column}>
        <Header onBack={onBack} onRefresh={() => void refetch()} isFetching={isFetching} />

        <div className={styles.table}>
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
    <div className={styles.header}>
      <button type="button" onClick={onBack} className={styles.chromeButton}>
        {Ic.arrowLeft(15)} Back
      </button>
      <div className={styles.headings}>
        <h1 className={styles.title}>Workbench Agents</h1>
        <p className={styles.subtitle}>Runners currently dialed into this control plane</p>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        title="Refresh"
        className={styles.chromeButton}
        data-busy={isFetching || undefined}
      >
        {Ic.refresh(15)} Refresh
      </button>
    </div>
  );
}

function HeaderRow() {
  return (
    <div className={styles.row} data-kind="head">
      <div className={styles.headCell}>Host</div>
      <div className={styles.headCell}>Agent ID</div>
      <div className={styles.headCell}>Runtime</div>
      <div className={styles.headCell}>Version</div>
      <div className={styles.headCell}>Connected</div>
    </div>
  );
}

function AgentRow({ agent, nowMs }: { agent: Agent; nowMs: number }) {
  const uptime = formatDuration(connectedDurationMs(agent, nowMs));
  return (
    <div className={styles.row}>
      <div className={styles.host}>
        <span className={styles.hostIcon} title="Connected">
          {Ic.cpu(15)}
        </span>
        <span className={styles.hostName}>{agent.hostname || "—"}</span>
      </div>
      <div className={styles.cell} data-flavor="code">
        {agent.id}
      </div>
      <div className={styles.cell}>{agent.dockerMode || "—"}</div>
      <div className={styles.cell} data-flavor="code">
        {agent.version || "—"}
      </div>
      <div className={styles.uptime}>
        <span aria-hidden className={styles.uptimeDot} />
        <span className={styles.cell}>{uptime}</span>
      </div>
    </div>
  );
}

function StatusRow({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div className={styles.statusRow} data-tone={tone}>
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
        Start one pointing at this control plane:
        <br />
        <code>WORKBENCH_API_WS_URL=ws://…/agent/connect python -m repo2ree_agent</code>
      </div>
    </div>
  );
}
