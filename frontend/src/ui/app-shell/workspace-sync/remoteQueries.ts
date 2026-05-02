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
} from "../../../application/ports/repositoryTypes";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
import type { WorkspaceRepository } from "../../../application/ports/WorkspaceRepository";
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
  workspaceRepository: WorkspaceRepository<FileTreeNode>,
  workspaceId: string,
) {
  return queryOptions({
    queryKey: workspaceQueryKey(workspaceId),
    queryFn: () => workspaceRepository.getWorkspace(workspaceId),
  });
}

function workflowRunQueryOptions(
  workflowRunRepository: WorkflowRunRepository,
  workspaceId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: workflowRunQueryKey(workspaceId, runId),
    queryFn: () => workflowRunRepository.getWorkflowRun(workspaceId, runId),
  });
}

function workflowRunLogsQueryOptions(
  workflowRunRepository: WorkflowRunRepository,
  workspaceId: string,
  runId: string,
  cursor?: string,
) {
  return queryOptions({
    queryKey: workflowRunLogsQueryKey(workspaceId, runId, cursor),
    queryFn: () => workflowRunRepository.getWorkflowRunLogs(workspaceId, runId, cursor),
  });
}

interface UseWorkspaceQueryArgs {
  workspaceRepository: WorkspaceRepository<FileTreeNode>;
  workspaceId: string;
  enabled?: boolean;
}

export function useWorkspaceQuery({
  workspaceRepository,
  workspaceId,
  enabled = false,
}: UseWorkspaceQueryArgs) {
  const queryClient = useQueryClient();
  const query = useQuery({
    ...workspaceQueryOptions(workspaceRepository, workspaceId),
    enabled,
  });
  const refresh = useCallback(
    () => queryClient.fetchQuery(workspaceQueryOptions(workspaceRepository, workspaceId)),
    [queryClient, workspaceId, workspaceRepository],
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
  workspaceRepository: WorkspaceRepository<FileTreeNode>;
  workspaceId: string;
}

export function useUpdateReeDraftMutation({
  workspaceRepository,
  workspaceId,
}: UpdateReeDraftMutationArgs) {
  return useMutation({
    mutationFn: (reePatch: Record<string, unknown>) =>
      workspaceRepository.updateReeDraft(workspaceId, reePatch),
  });
}

interface UseWorkflowRunQueryArgs {
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
  runId: string | null;
  enabled?: boolean;
}

export function useWorkflowRunQuery({
  workflowRunRepository,
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
      return workflowRunRepository.getWorkflowRun(workspaceId, runId);
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
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
  runId: string | null;
  cursor?: string;
  enabled?: boolean;
}

export function useWorkflowRunLogsQuery({
  workflowRunRepository,
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
      return workflowRunRepository.getWorkflowRunLogs(workspaceId, runId, cursor);
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
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
}

export function useStartWorkflowRunMutation({
  workflowRunRepository,
  workspaceId,
}: StartWorkflowRunMutationArgs) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ scriptKey, params = {} }: { scriptKey: string; params?: WorkflowRunParams }) =>
      workflowRunRepository.startWorkflowRun(workspaceId, scriptKey, params),
    onSuccess: (run) => {
      queryClient.setQueryData(workflowRunQueryKey(workspaceId, run.runId), run);
    },
  });
}

interface CancelWorkflowRunMutationArgs {
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
}

export function useCancelWorkflowRunMutation({
  workflowRunRepository,
  workspaceId,
}: CancelWorkflowRunMutationArgs) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      const status = await workflowRunRepository.cancelWorkflowRun(workspaceId, runId);
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
  workflowRunRepository: WorkflowRunRepository,
  workspaceId: string,
  runId: string,
): Promise<WorkflowRunRecord> {
  return queryClient.fetchQuery(workflowRunQueryOptions(workflowRunRepository, workspaceId, runId));
}

export async function fetchWorkflowRunLogs(
  queryClient: QueryClient,
  workflowRunRepository: WorkflowRunRepository,
  workspaceId: string,
  runId: string,
  cursor?: string,
): Promise<WorkflowRunLogChunk> {
  return queryClient.fetchQuery(
    workflowRunLogsQueryOptions(workflowRunRepository, workspaceId, runId, cursor),
  );
}
