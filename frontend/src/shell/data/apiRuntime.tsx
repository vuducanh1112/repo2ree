import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";
import { isTerminalExecutionRunStatus } from "../../core/execution/ExecutionRunStatus";
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

const PROVISION_POLL_INTERVAL_MS = 1500;
// Cap the wait so a run that never reaches a terminal status (server restart
// mid-provision, dropped run state) surfaces as an error instead of spinning
// this headless poller forever. A cold image pull is the slow case, so the
// budget is generous.
const PROVISION_POLL_TIMEOUT_MS = 10 * 60 * 1000;

// Status-only waiter for the background provisioning run. This sits at the raw
// ExecutionRunsApi layer (no QueryClient / ExecutionRunsClient), so it can't use
// observeExecutionRun — that's the log-streaming poller for UI callers. Here we
// only need the terminal status to return a ready reeId from ensureReeId.
async function waitForRunCompletion(
  runsApi: ExecutionRunsApi,
  reeId: string,
  runId: string,
): Promise<string> {
  const deadline = Date.now() + PROVISION_POLL_TIMEOUT_MS;
  while (true) {
    const run = await runsApi.getRun(reeId, runId);
    if (isTerminalExecutionRunStatus(run.status)) {
      return run.status;
    }
    if (Date.now() >= deadline) {
      throw new Error("Timed out waiting for workbench provisioning to finish");
    }
    await new Promise((resolve) => setTimeout(resolve, PROVISION_POLL_INTERVAL_MS));
  }
}

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
    const run = await reeApi.createRee({
      sourceMode: "upload",
      name: "REE Workspace",
    });
    // Provisioning is a background run (the image pull streams live); wait for
    // it to finish so callers get a workbench that's actually ready to use.
    const status = await waitForRunCompletion(runsApi, run.reeId, run.runId);
    if (status !== "succeeded") {
      throw new Error(`Workbench provisioning ${status}`);
    }
    resolvedReeId = asReeId(run.reeId);
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
