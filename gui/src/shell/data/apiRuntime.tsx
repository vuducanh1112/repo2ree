import { createContext, type ReactNode, useContext, useMemo } from "react";
import { asReeId, type ReeId } from "../../core/ree/ReeId";
import { ApiClient } from "../infra/api/ApiClient";
import { ReeApi } from "../infra/api/ReeApi";
import { ReeRunsApi } from "../infra/api/ReeRunsApi";

export interface ApiServicesValue {
  reeApi: ReeApi;
  runsApi: ReeRunsApi;
}

export interface ReeRuntimeValue extends ApiServicesValue {
  reeId: ReeId;
}

const ApiServicesContext = createContext<ApiServicesValue | null>(null);
const ReeScopeContext = createContext<ReeId | null>(null);

export function createApiServices({ baseUrl = "" }: { baseUrl?: string } = {}): ApiServicesValue {
  const client = new ApiClient({ baseUrl });
  return {
    reeApi: new ReeApi(client),
    runsApi: new ReeRunsApi(client),
  };
}

export function ApiServicesProvider({
  children,
  baseUrl,
  services,
}: {
  children: ReactNode;
  baseUrl?: string;
  /** Test/composition seam; production creates the services from `baseUrl`. */
  services?: ApiServicesValue;
}) {
  const created = useMemo(() => createApiServices({ baseUrl }), [baseUrl]);
  const value = services ?? created;
  return <ApiServicesContext.Provider value={value}>{children}</ApiServicesContext.Provider>;
}

export function ReeScopeProvider({ children, reeId }: { children: ReactNode; reeId: string }) {
  const value = useMemo(() => asReeId(reeId), [reeId]);
  return <ReeScopeContext.Provider value={value}>{children}</ReeScopeContext.Provider>;
}

export function useApiServices(): ApiServicesValue {
  const value = useContext(ApiServicesContext);
  if (!value) {
    throw new Error("useApiServices must be used within ApiServicesProvider");
  }
  return value;
}

export function useReeId(): ReeId {
  const reeId = useContext(ReeScopeContext);
  if (!reeId) {
    throw new Error("useReeId must be used within ReeScopeProvider");
  }
  return reeId;
}

/** Convenience adapter for code that needs both independent contexts. */
export function useReeRuntime(): ReeRuntimeValue {
  const services = useApiServices();
  const reeId = useReeId();
  return useMemo(() => ({ ...services, reeId }), [services, reeId]);
}
