import type { QueryClient } from "@tanstack/react-query";
import { queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useWorkspaceRuntime, type WorkspaceRuntimeValue } from "../../app/browser/BrowserRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";

function createReeQueryOptions(runtime: WorkspaceRuntimeValue, workspaceId?: string) {
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);
  return queryOptions({
    queryKey: queryKeys.ree(resolvedWorkspaceId),
    queryFn: () => runtime.workspaceRepository.getWorkspace(resolvedWorkspaceId),
  });
}

async function fetchReeQuery(
  queryClient: QueryClient,
  runtime: WorkspaceRuntimeValue,
  workspaceId?: string,
) {
  return queryClient.fetchQuery(createReeQueryOptions(runtime, workspaceId));
}

export function useReeQuery({
  workspaceId,
  enabled = true,
}: {
  workspaceId?: string;
  enabled?: boolean;
} = {}) {
  const runtime = useWorkspaceRuntime();
  return useQuery({
    ...createReeQueryOptions(runtime, workspaceId),
    enabled,
  });
}

export function useRefreshReeQuery(workspaceId?: string) {
  const runtime = useWorkspaceRuntime();
  const queryClient = useQueryClient();

  return useCallback(
    () => fetchReeQuery(queryClient, runtime, workspaceId),
    [queryClient, runtime, workspaceId],
  );
}
