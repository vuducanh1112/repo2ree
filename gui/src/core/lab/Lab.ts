// A lab is a store: a directory of REEs on some machine, served by one workbench that dials
// into the control plane. Pure domain shape; the data layer maps the API wire shape onto this.
// Every registered store is listed, served or not: an offline lab keeps its REEs, but no new
// one can be created there until its workbench is back.
export type LabStatus = "connected" | "offline";

export interface Lab {
  id: string;
  label: string;
  description: string;
  /** How its machine runs each REE's scripts. Unknown while no workbench serves the lab. */
  machine: LabMachine | null;
  status: LabStatus;
  available: boolean;
  /** The serving workbench's build, while one serves the lab. */
  build?: { version?: string; revision?: string };
}

// How a lab's machine runs an REE's scripts, as `ree machine` reports it there.
export interface LabMachine {
  /** The engine it enters the image an REE declares with; "none" when it has none. */
  engine: "docker" | "podman" | "apptainer" | "none";
}

/** How the lab runs scripts, in a few words: in an REE's image, or only on its own machine. */
export function describeMachine(machine: LabMachine | null): string {
  if (!machine) return "—";
  return machine.engine === "none" ? "its own machine only" : `images with ${machine.engine}`;
}

// Stable display order: by label, then id. Pure; returns a new array.
export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
