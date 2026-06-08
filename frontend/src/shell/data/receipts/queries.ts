import { useQuery } from "@tanstack/react-query";
import type { ActionReceipt } from "../../../core/ree/ReeTypes";
import { useApiRuntime } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

export function useReceiptsQuery(reeId: string | undefined): {
  data: ActionReceipt[] | undefined;
  isLoading: boolean;
  error: unknown;
} {
  const { reeApi } = useApiRuntime();
  const resolvedReeId = reeId ?? "";
  return useQuery({
    queryKey: queryKeys.receipts(resolvedReeId),
    queryFn: () => reeApi.getReceipts(resolvedReeId),
    enabled: !!reeId,
    staleTime: 10_000,
  });
}
