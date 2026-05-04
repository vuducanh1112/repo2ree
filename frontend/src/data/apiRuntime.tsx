import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";
import { DEFAULT_REE_ID } from "../app/config/ReeConstants";
import { asReeId, type ReeId } from "../domain/ree/ReeId";
import { ApiClient } from "../infra/api/ApiClient";
import { ReeApi } from "../infra/api/ReeApi";
import { ReviewsApi } from "../infra/api/ReviewsApi";
import { WorkflowRunsApi } from "../infra/api/WorkflowRunsApi";

export interface ApiRuntimeValue {
  reeId: ReeId;
  ensureReeId: (requestedId: ReeId | string) => Promise<ReeId>;
  reeApi: ReeApi;
  runsApi: WorkflowRunsApi;
  reviewsApi: ReviewsApi;
}

interface ApiClientProviderProps {
  children: ReactNode;
  baseUrl?: string;
  initialReeId?: string;
  reeId?: string;
}

const ApiRuntimeContext = createContext<ApiRuntimeValue | null>(null);

function createApiRuntime({
  baseUrl,
  initialReeId,
  reeId,
}: {
  baseUrl?: string;
  initialReeId?: string;
  reeId?: string;
}): ApiRuntimeValue {
  const client = new ApiClient({ baseUrl });
  const reeApi = new ReeApi(client);
  const runsApi = new WorkflowRunsApi(client);
  const reviewsApi = new ReviewsApi(client);
  let resolvedReeId: ReeId | null = initialReeId ? asReeId(initialReeId) : null;

  const ensureReeId = async (requestedId: ReeId | string): Promise<ReeId> => {
    if (requestedId && requestedId !== DEFAULT_REE_ID) {
      return asReeId(String(requestedId));
    }
    if (resolvedReeId) {
      return resolvedReeId;
    }
    const created = await reeApi.createRee({
      sourceMode: "upload",
      name: "REE Workspace",
    });
    resolvedReeId = asReeId(created.reeId);
    return resolvedReeId;
  };

  return {
    reeId: reeId ? asReeId(reeId) : DEFAULT_REE_ID,
    ensureReeId,
    reeApi,
    runsApi,
    reviewsApi,
  };
}

export function ApiClientProvider({
  children,
  baseUrl,
  initialReeId,
  reeId,
}: ApiClientProviderProps) {
  const value = useMemo(
    () =>
      createApiRuntime({
        baseUrl,
        initialReeId,
        reeId,
      }),
    [baseUrl, initialReeId, reeId],
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
