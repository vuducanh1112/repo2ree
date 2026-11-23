import type { Lab } from "@core/lab/Lab";
import { sortLabs } from "@core/lab/Lab";
import type { StoreSummary } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

function mapLab(wire: StoreSummary): Lab {
  return {
    id: wire.store_id,
    label: wire.label,
    description: "",
    machine: wire.machine
      ? {
          arch: wire.machine.arch ?? "",
          gpus: wire.machine.gpus ?? 0,
        }
      : null,
    status: wire.connected ? "connected" : "offline",
    available: wire.connected,
    build: wire.build ?? undefined,
  };
}

const LABS_REFETCH_MS = 5000;

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
