import type { Lab } from "@core/lab/Lab";
import { sortLabs } from "@core/lab/Lab";
import type { StoreSummary } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure wire shape → domain map. A store is listed whether or not a workbench serves it; it is
// available for a new REE only while one does.
function mapLab(wire: StoreSummary): Lab {
  return {
    id: wire.store_id,
    label: wire.label,
    description: "",
    backend: wire.backend ?? null,
    // The ref is the image's name: it is what the REE declares, and what a reviewer reruns in.
    images: (wire.images ?? []).map((ref) => ({ id: ref, ref, label: ref, description: "" })),
    status: wire.connected ? "connected" : "offline",
    available: wire.connected,
    build: wire.build ?? undefined,
  };
}

// The fleet drifts as labs dial in and drop, so poll rather than cache: a
// connect/disconnect should surface within a few seconds without a reload.
const LABS_REFETCH_MS = 5000;

// The stores registered here, kept fresh by polling. Backs the fleet-management pane. Each
// carries the images it offers, so this is one call.
export function useLabs() {
  const { reeApi } = useApiServices();
  return useQuery({
    queryKey: queryKeys.labs(),
    queryFn: async (): Promise<Lab[]> => {
      const listed = await reeApi.listStores();
      return sortLabs(listed.stores.map(mapLab));
    },
    refetchInterval: LABS_REFETCH_MS,
  });
}
