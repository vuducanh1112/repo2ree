import type { Lab } from "@core/lab/Lab";
import { sortLabs } from "@core/lab/Lab";
import type { ProviderSummary, WorkbenchSummary } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure wire shape → domain map. Status is narrowed to the domain's single connected
// state; the endpoint only lists connected labs.
function mapLab(wire: ProviderSummary): Lab {
  return {
    id: wire.provider_id,
    kind: "provider",
    hostname: wire.hostname,
    version: wire.version,
    dockerMode: wire.docker_mode,
    connectedAt: wire.connected_at,
    status: "connected",
    available: true,
  };
}

function mapExternalLab(wire: WorkbenchSummary): Lab {
  return {
    id: wire.workbench_id,
    kind: "external",
    hostname: wire.hostname,
    version: wire.version,
    dockerMode: wire.docker_mode,
    connectedAt: wire.connected_at,
    status: "connected",
    available: wire.available,
  };
}

// The fleet drifts as labs dial in and drop, so poll rather than cache: a
// connect/disconnect should surface within a few seconds without a reload.
const LABS_REFETCH_MS = 5000;

// Workbench labs currently connected to the control plane, kept fresh by
// polling. Backs the fleet-management pane.
export function useLabs() {
  const { reeApi } = useApiServices();
  return useQuery({
    queryKey: queryKeys.labs(),
    queryFn: async (): Promise<Lab[]> => {
      const [providers, workbenches] = await Promise.all([
        reeApi.listProviders(),
        reeApi.listWorkbenches(),
      ]);
      return sortLabs([
        ...providers.providers.map(mapLab),
        ...workbenches.workbenches.filter((bench) => bench.mode === "external").map(mapExternalLab),
      ]);
    },
    refetchInterval: LABS_REFETCH_MS,
  });
}
