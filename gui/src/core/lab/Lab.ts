// A lab location represented by a workbench service dialed into the control plane.
// Pure domain shape; the data layer maps the API wire shape onto this. A lab is listed only while it holds its
// outbound connection, so `status` is "connected" for everything the fleet view
// receives — the field exists so a later broker step can add drained/draining.
export type LabStatus = "connected";

export interface Lab {
  id: string;
  label: string;
  description: string;
  lifecycleMode: "provider_managed" | "externally_managed";
  profiles: ComputeProfile[];
  status: LabStatus;
  available: boolean;
}

export interface ComputeProfile {
  id: string;
  revision: string;
  label: string;
  description: string;
  substrate: "bare" | "docker-nested" | "docker-host-socket";
  cpuCount?: number;
  memoryBytes?: number;
  storagePolicy: "ephemeral" | "retained" | "external";
}

// Stable display order: by label, then id. Pure; returns a new array.
export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
