export type LabStatus = "connected" | "offline";

export interface Lab {
  id: string;
  label: string;
  description: string;
  machine: LabMachine | null;
  status: LabStatus;
  available: boolean;
  build?: { version?: string; revision?: string };
}

export interface LabMachine {
  arch: string;
  gpus: number;
}

export function describeMachine(machine: LabMachine | null): string {
  if (!machine) return "—";
  const gpus = machine.gpus > 0 ? `, ${machine.gpus} GPU${machine.gpus === 1 ? "" : "s"}` : "";
  return `${machine.arch || "unknown"}${gpus}`;
}

export function sortLabs(labs: readonly Lab[]): Lab[] {
  return [...labs].sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
