// A lab is a store: a directory of REEs on some machine, served by one workbench that dials
// into the control plane. Pure domain shape; the data layer maps the API wire shape onto this.
// Every registered store is listed, served or not: an offline lab keeps its REEs, but no new
// one can be created there until its workbench is back.
export type LabStatus = "connected" | "offline";

export interface Lab {
  id: string;
  label: string;
  description: string;
  /**
   * Where its workbench runs each REE's scripts: in a fresh container from the image the REE
   * declares, or on its own machine. Unknown while no workbench serves the lab.
   */
  backend: "container" | "host" | null;
  /** The images a new REE here may declare, the first the default. Empty on a host lab. */
  images: WorkbenchImage[];
  status: LabStatus;
  available: boolean;
  /** The serving workbench's build, while one serves the lab. */
  build?: { version?: string; revision?: string };
}

// One image a lab offers. `ref` is what the REE declares; the rest names the entry in the
// picker.
export interface WorkbenchImage {
  id: string;
  ref: string;
  label: string;
  description: string;
}

// Stable display order: by label, then id. Pure; returns a new array.
export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
