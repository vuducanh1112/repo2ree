import {
  type QueryClient,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useCallback } from "react";
import type {
  ReeProject,
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkspaceBackendGateway,
} from "../../../application/ports/WorkspaceBackendGateway";
import { toRemoteResourceState } from "../../../application/remote-resource/RemoteResourceState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";

type WorkflowRunParams = Record<string, string | boolean | number | null | undefined>;

function workspaceQueryKey(workspaceId: string) {
  return ["workspace", workspaceId] as const;
}

function workflowRunQueryKey(workspaceId: string, runId: string) {
  return ["workspace", workspaceId, "workflow-run", runId] as const;
}

function workflowRunLogsQueryKey(workspaceId: string, runId: string, cursor?: string) {
  return ["workspace", workspaceId, "workflow-run", runId, "logs", cursor || "0"] as const;
}

function workspaceQueryOptions(
  workspaceService: WorkspaceBackendGateway<FileTreeNode>,
  workspaceId: string,
) {
  return queryOptions({
    queryKey: workspaceQueryKey(workspaceId),
    queryFn: () => workspaceService.getWorkspace(workspaceId),
  });
}

function workflowRunQueryOptions(
  workspaceService: WorkspaceBackendGateway<FileTreeNode>,
  workspaceId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: workflowRunQueryKey(workspaceId, runId),
    queryFn: async () => {
      if (!workspaceService.getWorkflowRun) {
        throw new Error("Workflow polling is not supported by this workflow backend");
      }
      return workspaceService.getWorkflowRun(workspaceId, runId);
    },
  });
}

function workflowRunLogsQueryOptions(
  workspaceService: WorkspaceBackendGateway<FileTreeNode>,
  workspaceId: string,
  runId: string,
  cursor?: string,
) {
  return queryOptions({
    queryKey: workflowRunLogsQueryKey(workspaceId, runId, cursor),
    queryFn: async () => {
      if (!workspaceService.getWorkflowRunLogs) {
        return { lines: [], hasMore: false } satisfies WorkflowRunLogChunk;
      }
      return workspaceService.getWorkflowRunLogs(workspaceId, runId, cursor);
    },
  });
}

interface UseWorkspaceQueryArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
  enabled?: boolean;
}

export function useWorkspaceQuery({
  workspaceService,
  workspaceId,
  enabled = false,
}: UseWorkspaceQueryArgs) {
  const queryClient = useQueryClient();
  const query = useQuery({
    ...workspaceQueryOptions(workspaceService, workspaceId),
    enabled,
  });
  const refresh = useCallback(
    () => queryClient.fetchQuery(workspaceQueryOptions(workspaceService, workspaceId)),
    [queryClient, workspaceId, workspaceService],
  );

  return {
    ...query,
    resourceState: toRemoteResourceState<ReeProject<FileTreeNode>>({
      data: query.data,
      error: query.error,
      isPending: query.isPending,
      isFetching: query.isFetching,
    }),
    refresh,
  };
}

interface UpdateReeDraftMutationArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
}

export function useUpdateReeDraftMutation({
  workspaceService,
  workspaceId,
}: UpdateReeDraftMutationArgs) {
  return useMutation({
    mutationFn: async (reePatch: Record<string, unknown>) => {
      if (!workspaceService.updateReeDraft) {
        throw new Error("Workspace backend does not support REE draft updates");
      }
      await workspaceService.updateReeDraft(workspaceId, reePatch);
    },
  });
}

interface UseWorkflowRunQueryArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
  runId: string | null;
  enabled?: boolean;
}

export function useWorkflowRunQuery({
  workspaceService,
  workspaceId,
  runId,
  enabled = false,
}: UseWorkflowRunQueryArgs) {
  const query = useQuery<WorkflowRunRecord, Error>({
    queryKey: workflowRunQueryKey(workspaceId, runId || "idle"),
    queryFn: async () => {
      if (!runId) {
        throw new Error("Workflow run query is disabled");
      }
      if (!workspaceService.getWorkflowRun) {
        throw new Error("Workflow polling is not supported by this workflow backend");
      }
      return workspaceService.getWorkflowRun(workspaceId, runId);
    },
    enabled: enabled && !!runId,
  });

  return {
    ...query,
    resourceState: toRemoteResourceState<WorkflowRunRecord>({
      data: query.data,
      error: query.error,
      isPending: query.isPending,
      isFetching: query.isFetching,
    }),
  };
}

interface UseWorkflowRunLogsQueryArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
  runId: string | null;
  cursor?: string;
  enabled?: boolean;
}

export function useWorkflowRunLogsQuery({
  workspaceService,
  workspaceId,
  runId,
  cursor,
  enabled = false,
}: UseWorkflowRunLogsQueryArgs) {
  const query = useQuery<WorkflowRunLogChunk, Error>({
    queryKey: workflowRunLogsQueryKey(workspaceId, runId || "idle", cursor),
    queryFn: async () => {
      if (!runId) {
        throw new Error("Workflow run logs query is disabled");
      }
      if (!workspaceService.getWorkflowRunLogs) {
        return { lines: [], hasMore: false };
      }
      return workspaceService.getWorkflowRunLogs(workspaceId, runId, cursor);
    },
    enabled: enabled && !!runId,
  });

  return {
    ...query,
    resourceState: toRemoteResourceState<WorkflowRunLogChunk>({
      data: query.data,
      error: query.error,
      isPending: query.isPending,
      isFetching: query.isFetching,
    }),
  };
}

interface StartWorkflowRunMutationArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
}

export function useStartWorkflowRunMutation({
  workspaceService,
  workspaceId,
}: StartWorkflowRunMutationArgs) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      scriptKey,
      params = {},
    }: {
      scriptKey: string;
      params?: WorkflowRunParams;
    }) => {
      if (!workspaceService.startWorkflowRun) {
        throw new Error("Workspace backend does not support workflow runs");
      }
      return workspaceService.startWorkflowRun(workspaceId, scriptKey, params);
    },
    onSuccess: (run) => {
      queryClient.setQueryData(workflowRunQueryKey(workspaceId, run.runId), run);
    },
  });
}

interface CancelWorkflowRunMutationArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
}

export function useCancelWorkflowRunMutation({
  workspaceService,
  workspaceId,
}: CancelWorkflowRunMutationArgs) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      if (!workspaceService.cancelWorkflowRun) {
        throw new Error("Workspace backend does not support workflow cancellation");
      }
      const status = await workspaceService.cancelWorkflowRun(workspaceId, runId);
      return { runId, status };
    },
    onSuccess: ({ runId, status }) => {
      queryClient.setQueryData<WorkflowRunRecord | undefined>(
        workflowRunQueryKey(workspaceId, runId),
        (existing) => (existing ? { ...existing, status } : existing),
      );
    },
  });
}

export async function fetchWorkflowRun(
  queryClient: QueryClient,
  workspaceService: WorkspaceBackendGateway<FileTreeNode>,
  workspaceId: string,
  runId: string,
): Promise<WorkflowRunRecord> {
  return queryClient.fetchQuery(workflowRunQueryOptions(workspaceService, workspaceId, runId));
}

export async function fetchWorkflowRunLogs(
  queryClient: QueryClient,
  workspaceService: WorkspaceBackendGateway<FileTreeNode>,
  workspaceId: string,
  runId: string,
  cursor?: string,
): Promise<WorkflowRunLogChunk> {
  return queryClient.fetchQuery(
    workflowRunLogsQueryOptions(workspaceService, workspaceId, runId, cursor),
  );
}
