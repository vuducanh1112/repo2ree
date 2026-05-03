import type { QueryClient } from "@tanstack/react-query";
import { queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";
import type { WorkspaceClient } from "./client";
import { useWorkspaceClient } from "./client";

function createReeQueryOptions(
  runtime: ApiRuntimeValue,
  workspaceClient: WorkspaceClient<FileTreeNode>,
  workspaceId?: string,
) {
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);
  return queryOptions({
    queryKey: queryKeys.ree(resolvedWorkspaceId),
    queryFn: () => workspaceClient.getWorkspace(resolvedWorkspaceId),
  });
}

async function fetchReeQuery(
  queryClient: QueryClient,
  runtime: ApiRuntimeValue,
  workspaceClient: WorkspaceClient<FileTreeNode>,
  workspaceId?: string,
) {
  return queryClient.fetchQuery(createReeQueryOptions(runtime, workspaceClient, workspaceId));
}

export function useReeQuery({
  workspaceId,
  enabled = true,
}: {
  workspaceId?: string;
  enabled?: boolean;
} = {}) {
  const runtime = useApiRuntime();
  const workspaceClient = useWorkspaceClient();
  return useQuery({
    ...createReeQueryOptions(runtime, workspaceClient, workspaceId),
    enabled,
  });
}

export function useRefreshReeQuery(workspaceId?: string) {
  const runtime = useApiRuntime();
  const workspaceClient = useWorkspaceClient();
  const queryClient = useQueryClient();

  return useCallback(
    () => fetchReeQuery(queryClient, runtime, workspaceClient, workspaceId),
    [queryClient, runtime, workspaceClient, workspaceId],
  );
}
