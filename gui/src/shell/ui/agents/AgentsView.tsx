import type { Agent } from "@core/agent/Agent";
import { connectedDurationMs, formatDuration } from "@core/agent/Agent";
import { useAgents } from "@shell/data/agents/agents";
import { Ic } from "../shared/components/Icon";
import styles from "./AgentsView.module.css";
import { agentLoadErrorMessage } from "./agentPresentation";
import { NoAgentsState } from "./NoAgentsState";
import { useAgentUptimeClock } from "./useAgentUptimeClock";

interface AgentsViewProps {
  onBack: () => void;
}

export function AgentsView({ onBack }: AgentsViewProps) {
  const { data: agents, isLoading, isError, error, refetch, isFetching } = useAgents();

  const nowMs = useAgentUptimeClock(Boolean(agents?.length));

  return (
    <div className={styles.screen}>
      <div className={styles.column}>
        <Header onBack={onBack} onRefresh={() => void refetch()} isFetching={isFetching} />

        <div className={styles.table}>
          <HeaderRow />
          {isLoading ? (
            <StatusRow text="Loading agents…" />
          ) : isError ? (
            <StatusRow text={agentLoadErrorMessage(error)} tone="error" />
          ) : !agents || agents.length === 0 ? (
            <NoAgentsState description="Start one pointing at this control plane:" />
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
    <div className={styles.statusRow} data-tone={tone} role={tone === "error" ? "alert" : "status"}>
      {text}
    </div>
  );
}
