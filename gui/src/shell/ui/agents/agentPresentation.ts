export function agentLoadErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : "unknown error";
  return `Failed to load agents: ${detail}`;
}

interface DockerModeCopy {
  /** The readout value — two words at most, so it fits a cell's meta line. */
  readout: string;
  /** What picking this lab means for the author, in one sentence. */
  line: string;
}

/**
 * Turns the agent's `docker_mode` into something an author can decide on. The
 * wire value names an implementation; a person choosing where their work runs
 * needs to know what it costs them.
 */
export function dockerModeCopy(mode: string): DockerModeCopy {
  if (mode === "dind") {
    return {
      readout: "per-workbench",
      line: "Isolated Docker per workbench — nothing shared with other work on this machine.",
    };
  }
  if (mode === "host") {
    return {
      readout: "shared daemon",
      line: "Shares this machine's Docker — starts faster, sits alongside other work.",
    };
  }
  // Never invent a description for a mode we don't recognise: show the raw
  // value and say only what is true of every lab.
  return { readout: mode || "—", line: "Hosts this REE's workbench." };
}
