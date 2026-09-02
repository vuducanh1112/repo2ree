// A lab location represented by a workbench service dialed into the control plane.
// Pure domain shape; the data layer maps the API wire shape onto this. A lab is listed only while it holds its
// outbound connection, so `status` is "connected" for everything the fleet view
// receives — the field exists so a later broker step can add drained/draining.
export type LabStatus = "connected";

export interface Lab {
  id: string;
  kind: "provider" | "external";
  hostname: string;
  version: string;
  dockerMode: string;
  /** ISO 8601 timestamp of when the lab dialed in. */
  connectedAt: string;
  status: LabStatus;
  available: boolean;
}

// Milliseconds a lab has been connected, given the current wall clock. Pure;
// returns 0 for an unparseable or future timestamp.
export function connectedDurationMs(lab: Lab, nowMs: number): number {
  const since = Date.parse(lab.connectedAt);
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
export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.hostname.localeCompare(b.hostname) || a.id.localeCompare(b.id));
}
