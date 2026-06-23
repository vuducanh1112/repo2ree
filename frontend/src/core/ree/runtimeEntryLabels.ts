import type { ContainerEngine, RuntimeEntry } from "./ReeSpec";

export const ENGINE_LABELS: Record<ContainerEngine, string> = {
  docker: "Docker",
  podman: "Podman",
  apptainer: "Apptainer",
};

export const CONTAINER_ENGINES: readonly ContainerEngine[] = ["docker", "podman", "apptainer"];

/** Short human label for the substrate kind + engine, e.g. "Docker container" */
export function substrateLabel(entry: RuntimeEntry): string {
  switch (entry.kind) {
    case "container":
      return `${ENGINE_LABELS[entry.engine]} container`;
    case "local":
      return entry.activate ? "Local (venv)" : "Local";
    case "vm":
      return "Virtual machine";
    case "custom":
      return "Custom driver";
  }
}
