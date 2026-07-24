import type { AuthorReceiptSetWire } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useAuthorReceiptsQuery({ enabled = true }: { enabled?: boolean } = {}) {
  const runtime = useApiRuntime();
  const reeId = resolveReeId(runtime);

  return useQuery<AuthorReceiptSetWire>({
    queryKey: queryKeys.authorReceipts(reeId),
    queryFn: () => runtime.reeApi.listAuthorReceipts(reeId),
    enabled: enabled && !!runtime.reeId,
  });
}
