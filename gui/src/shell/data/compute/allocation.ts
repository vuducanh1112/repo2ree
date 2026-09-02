import type { AllocationRecord } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Obtaining a workbench runs through provisioning and a capability check before
// it is assigned, so an unsettled allocation is polled: the bench readout should
// reach its terminal state on its own, without a reload.
const ALLOCATION_REFETCH_MS = 2000;

const SETTLED: ReadonlySet<string> = new Set([
  "assigned",
  "released",
  "incompatible",
  "failed",
  "lost",
]);

/** The lifecycle record behind one REE's workbench, or idle until it has one. */
export function useAllocation(allocationId?: string) {
  const { reeApi } = useApiServices();
  return useQuery({
    queryKey: queryKeys.allocation(allocationId ?? ""),
    queryFn: (): Promise<AllocationRecord> => reeApi.getAllocation(allocationId as string),
    enabled: Boolean(allocationId),
    refetchInterval: (query) =>
      query.state.data && SETTLED.has(query.state.data.state) ? false : ALLOCATION_REFETCH_MS,
  });
}
