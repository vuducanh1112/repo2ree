import type { QueryClient } from "@tanstack/react-query";
import { queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import type { ReeClient } from "./client";
import { useReeClient } from "./client";

function createReeQueryOptions<TRee>(
  runtime: ApiRuntimeValue,
  reeClient: ReeClient<FileTreeNode, TRee>,
  reeId?: string,
) {
  const resolvedReeId = resolveReeId(runtime, reeId);
  return queryOptions({
    queryKey: queryKeys.ree(resolvedReeId),
    queryFn: () => reeClient.getRee(resolvedReeId),
  });
}

async function fetchReeQuery<TRee>(
  queryClient: QueryClient,
  runtime: ApiRuntimeValue,
  reeClient: ReeClient<FileTreeNode, TRee>,
  reeId?: string,
) {
  return queryClient.fetchQuery(createReeQueryOptions(runtime, reeClient, reeId));
}

export function useReeQuery({ reeId, enabled = true }: { reeId?: string; enabled?: boolean } = {}) {
  const runtime = useApiRuntime();
  const reeClient = useReeClient();
  return useQuery({
    ...createReeQueryOptions(runtime, reeClient, reeId),
    enabled,
  });
}

export function useRefreshReeQuery(reeId?: string) {
  const runtime = useApiRuntime();
  const reeClient = useReeClient();
  const queryClient = useQueryClient();

  return useCallback(
    () => fetchReeQuery(queryClient, runtime, reeClient, reeId),
    [queryClient, runtime, reeClient, reeId],
  );
}
