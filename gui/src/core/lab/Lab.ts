// A lab is a store: a directory of REEs on some machine, served by one workbench that dials
// into the control plane. Pure domain shape; the data layer maps the API wire shape onto this.
// Every registered store is listed, served or not: an offline lab keeps its REEs, but no new
// one can be created there until its workbench is back.
export type LabStatus = "connected" | "offline";

export interface Lab {
  id: string;
  label: string;
  description: string;
  /** The machine it runs each REE's scripts on. Unknown while no workbench serves the lab. */
  machine: LabMachine | null;
  status: LabStatus;
  available: boolean;
  /** The serving workbench's build, while one serves the lab. */
  build?: { version?: string; revision?: string };
}

// The machine a lab runs REEs' scripts on, as `ree machine` reports it there.
export interface LabMachine {
  arch: string;
  gpus: number;
  /** The image its provider says it runs in, when it says. */
  reportedImage: string | null;
}

/** The lab's machine, in a few words. */
export function describeMachine(machine: LabMachine | null): string {
  if (!machine) return "—";
  const gpus = machine.gpus > 0 ? `, ${machine.gpus} GPU${machine.gpus === 1 ? "" : "s"}` : "";
  return `${machine.arch || "unknown"}${gpus}${machine.reportedImage ? `, in ${machine.reportedImage}` : ""}`;
}

// Stable display order: by label, then id. Pure; returns a new array.
export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
