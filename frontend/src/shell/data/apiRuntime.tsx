import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";
import { asReeId, DEFAULT_REE_ID, type ReeId } from "../../core/ree/ReeId";
import { ApiClient } from "../infra/api/ApiClient";
import { ExecutionRunsApi } from "../infra/api/ExecutionRunsApi";
import { ReeApi } from "../infra/api/ReeApi";

export interface ApiRuntimeValue {
  reeId: ReeId;
  ensureReeId: (requestedId: ReeId | string) => Promise<ReeId>;
  reeApi: ReeApi;
  runsApi: ExecutionRunsApi;
}

interface ApiClientProviderProps {
  children: ReactNode;
  baseUrl?: string;
  initialReeId?: string;
  reeId?: string;
}

const ApiRuntimeContext = createContext<ApiRuntimeValue | null>(null);

export function createApiRuntime({
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
  const runsApi = new ExecutionRunsApi(client);
  const contextReeId = initialReeId
    ? asReeId(initialReeId)
    : reeId
      ? asReeId(reeId)
      : DEFAULT_REE_ID;
  let resolvedReeId: ReeId | null = contextReeId !== DEFAULT_REE_ID ? contextReeId : null;

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
    reeId: contextReeId,
    ensureReeId,
    reeApi,
    runsApi,
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
