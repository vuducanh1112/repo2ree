export function labLoadErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : "unknown error";
  return `Failed to load labs: ${detail}`;
}

interface DockerModeCopy {
  /** The readout value — two words at most, so it fits a cell's meta line. */
  readout: string;
  /** What picking this lab means for the author, in one sentence. */
  line: string;
}

/**
 * Turns the lab's `docker_mode` into something an author can decide on. The
 * wire value names an implementation; a person choosing where their work runs
 * needs to know what it costs them.
 */
export function dockerModeCopy(mode: string): DockerModeCopy {
  if (mode === "docker-nested") {
    return {
      readout: "per-workbench",
      line: "Isolated Docker per workbench — nothing shared with other work on this machine.",
    };
  }
  if (mode === "docker-host-socket") {
    return {
      readout: "shared daemon",
      line: "Shares this machine's Docker — starts faster, sits alongside other work.",
    };
  }
  // Never invent a description for a mode we don't recognise: show the raw
  // value and say only what is true of every lab.
  if (mode === "bare") {
    return { readout: "bare", line: "Provides command execution without a container daemon." };
  }
  return { readout: mode || "—", line: "Provides this REE's declared execution capabilities." };
}

/**
 * Names where a REE actually runs, for the ambient bench readouts. The
 * placement is a location and the fixed profile chosen there — never an image,
 * which is the provider's private business and is deliberately unreachable
 * from the browser.
 */
export function placementReadout(location?: string, profile?: string): string {
  if (location && profile) return `${profile} @ ${location}`;
  return profile || location || "Assigned profile";
}

// Keyed by the wire's own state names, so a Map rather than an object literal.
const ALLOCATION_STATE_COPY = new Map<string, string>([
  ["requested", "Requested"],
  ["provisioning", "Provisioning"],
  ["waiting_for_workbench", "Waiting for workbench"],
  ["ready", "Ready"],
  ["assigned", "Assigned"],
  ["draining", "Draining"],
  ["released", "Released"],
  ["incompatible", "Incompatible"],
  ["failed", "Failed"],
  ["lost", "Lost"],
]);

/**
 * How far obtaining this workbench has got. Unknown states are shown verbatim
 * rather than smoothed over: a control plane ahead of this build should read as
 * itself, not as "Ready".
 */
export function allocationStateCopy(state?: string): string {
  if (!state) return "—";
  return ALLOCATION_STATE_COPY.get(state) ?? state;
}
