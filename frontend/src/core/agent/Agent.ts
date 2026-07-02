// A workbench agent dialed into the control plane. Pure domain shape; the data
// layer maps the API DTO onto this. An agent is listed only while it holds its
// outbound connection, so `status` is "connected" for everything the fleet view
// receives — the field exists so a later broker step can add drained/draining.
export type AgentStatus = "connected";

export interface Agent {
  id: string;
  hostname: string;
  version: string;
  dockerMode: string;
  /** ISO 8601 timestamp of when the agent dialed in. */
  connectedAt: string;
  status: AgentStatus;
}

// Milliseconds an agent has been connected, given the current wall clock. Pure;
// returns 0 for an unparseable or future timestamp.
export function connectedDurationMs(agent: Agent, nowMs: number): number {
  const since = Date.parse(agent.connectedAt);
  if (Number.isNaN(since)) {
    return 0;
  }
  return Math.max(0, nowMs - since);
}

// Compact human label for a duration in ms: "45s", "12m", "3h", "5d". Pure.
export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h`;
  }
  return `${Math.floor(hours / 24)}d`;
}

// Stable display order: by hostname, then id. Pure; returns a new array.
export function sortAgents(agents: readonly Agent[]): Agent[] {
  return [...agents].sort(
    (a, b) => a.hostname.localeCompare(b.hostname) || a.id.localeCompare(b.id),
  );
}
