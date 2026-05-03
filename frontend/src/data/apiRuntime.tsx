import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";
import { WORKSPACE_ID } from "../app/config/WorkspaceConstants";
import { ApiClient } from "../infra/api/ApiClient";
import { ReviewsApi } from "../infra/api/ReviewsApi";
import { WorkflowRunsApi } from "../infra/api/WorkflowRunsApi";
import { WorkspaceApi } from "../infra/api/WorkspaceApi";

export interface ApiRuntimeValue {
  workspaceId: string;
  ensureWorkspaceId: (requestedId: string) => Promise<string>;
  workspaceApi: WorkspaceApi;
  runsApi: WorkflowRunsApi;
  reviewsApi: ReviewsApi;
}

interface ApiClientProviderProps {
  children: ReactNode;
  baseUrl?: string;
  initialWorkspaceId?: string;
  workspaceId?: string;
}

const ApiRuntimeContext = createContext<ApiRuntimeValue | null>(null);

function createApiRuntime({
  baseUrl,
  initialWorkspaceId,
  workspaceId,
}: {
  baseUrl?: string;
  initialWorkspaceId?: string;
  workspaceId?: string;
}): ApiRuntimeValue {
  const client = new ApiClient({ baseUrl });
  const workspaceApi = new WorkspaceApi(client);
  const runsApi = new WorkflowRunsApi(client);
  const reviewsApi = new ReviewsApi(client);
  let resolvedWorkspaceId: string | null = initialWorkspaceId || null;

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
    workspaceId: workspaceId || WORKSPACE_ID,
    ensureWorkspaceId,
    workspaceApi,
    runsApi,
    reviewsApi,
  };
}

export function ApiClientProvider({
  children,
  baseUrl,
  initialWorkspaceId,
  workspaceId,
}: ApiClientProviderProps) {
  const value = useMemo(
    () =>
      createApiRuntime({
        baseUrl,
        initialWorkspaceId,
        workspaceId,
      }),
    [baseUrl, initialWorkspaceId, workspaceId],
  );

  return <ApiRuntimeContext.Provider value={value}>{children}</ApiRuntimeContext.Provider>;
}

export function useApiRuntime(): ApiRuntimeValue {
  const value = useContext(ApiRuntimeContext);
  if (!value) {
    throw new Error("useApiRuntime must be used within ApiClientProvider");
  }
  return value;
}
