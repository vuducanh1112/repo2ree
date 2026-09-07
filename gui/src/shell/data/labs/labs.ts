import type { Lab } from "@core/lab/Lab";
import { sortLabs } from "@core/lab/Lab";
import type { ComputeLocation } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure wire shape → domain map. Status is narrowed to the domain's single connected
// state; the endpoint only lists connected labs.
function mapLab(wire: ComputeLocation): Lab {
  return {
    id: wire.id,
    label: wire.label,
    description: wire.description,
    lifecycleMode: wire.lifecycle_mode,
    images: (wire.images ?? []).map((image) => ({
      id: image.id,
      ref: image.ref,
      label: image.label,
      description: image.description,
    })),
    acceptsCustomImage: wire.accepts_custom_image ?? false,
    status: "connected",
    available: wire.available,
    connectedComponent: wire.connected_component
      ? {
          kind: wire.connected_component.kind,
          build: wire.connected_component.build ?? {},
        }
      : undefined,
  };
}

// The fleet drifts as labs dial in and drop, so poll rather than cache: a
// connect/disconnect should surface within a few seconds without a reload.
const LABS_REFETCH_MS = 5000;

// Workbench labs currently connected to the control plane, kept fresh by
// polling. Backs the fleet-management pane. Each location carries its own image
// catalog, so this is one call.
export function useLabs() {
  const { reeApi } = useApiServices();
  return useQuery({
    queryKey: queryKeys.labs(),
    queryFn: async (): Promise<Lab[]> => {
      const locations = await reeApi.listComputeLocations();
      return sortLabs(locations.locations.map(mapLab));
    },
    refetchInterval: LABS_REFETCH_MS,
  });
}
