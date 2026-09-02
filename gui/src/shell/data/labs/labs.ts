import type { Lab } from "@core/lab/Lab";
import { sortLabs } from "@core/lab/Lab";
import type { ComputeLocation, WorkbenchProfile } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure wire shape → domain map. Status is narrowed to the domain's single connected
// state; the endpoint only lists connected labs.
function mapLab(wire: ComputeLocation, profiles: readonly WorkbenchProfile[]): Lab {
  return {
    id: wire.id,
    label: wire.label,
    description: wire.description,
    lifecycleMode: wire.lifecycle_mode,
    profiles: profiles
      .filter((profile) => profile.location_id === wire.id)
      .map((profile) => ({
        id: profile.id,
        revision: profile.revision,
        label: profile.label,
        description: profile.description,
        substrate: profile.required.substrate,
        cpuCount: profile.required.resources?.cpu_count ?? undefined,
        memoryBytes: profile.required.resources?.memory_bytes ?? undefined,
        storagePolicy: profile.storage_policy,
      })),
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
      const [locations, profiles] = await Promise.all([
        reeApi.listComputeLocations(),
        reeApi.listWorkbenchProfiles(),
      ]);
      return sortLabs(locations.locations.map((location) => mapLab(location, profiles.profiles)));
    },
    refetchInterval: LABS_REFETCH_MS,
  });
}
