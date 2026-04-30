import { ApiClient } from "../api";
import { WorkflowRunsApi } from "../api/WorkflowRunsApi";
import { WorkspaceApi } from "../api/WorkspaceApi";

interface CreateHttpRepositoryClientOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
  initialWorkspaceId?: string;
}

export interface HttpRepositoryClient {
  workspaceApi: WorkspaceApi;
  runsApi: WorkflowRunsApi;
  ensureWorkspaceId: (requestedId: string) => Promise<string>;
}

export function createHttpRepositoryClient(
  options: CreateHttpRepositoryClientOptions = {},
): HttpRepositoryClient {
  const client = new ApiClient({
    baseUrl: options.baseUrl,
    headers: options.headers,
  });
  const workspaceApi = new WorkspaceApi(client);
  const runsApi = new WorkflowRunsApi(client);
  let resolvedWorkspaceId: string | null = options.initialWorkspaceId || null;

  const ensureWorkspaceId = async (requestedId: string): Promise<string> => {
    if (requestedId && requestedId !== "active") {
      return requestedId;
    }
    if (resolvedWorkspaceId) {
      return resolvedWorkspaceId;
    }

    const created = await workspaceApi.createWorkspace({
      sourceMode: "upload",
      name: "REE Workspace",
    });
    resolvedWorkspaceId = created.reeId;
    return created.reeId;
  };

  return {
    workspaceApi,
    runsApi,
    ensureWorkspaceId,
  };
}
