import type { Agent } from "@core/agent/Agent";
import { sortAgents } from "@core/agent/Agent";
import type { AgentSummary } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure wire shape → domain map. Status is narrowed to the domain's single connected
// state; the endpoint only lists connected agents.
function mapAgent(wire: AgentSummary): Agent {
  return {
    id: wire.agent_id,
    hostname: wire.hostname,
    version: wire.version,
    dockerMode: wire.docker_mode,
    connectedAt: wire.connected_at,
    status: "connected",
  };
}

// The fleet drifts as agents dial in and drop, so poll rather than cache: a
// connect/disconnect should surface within a few seconds without a reload.
const AGENTS_REFETCH_MS = 5000;

// Workbench agents currently connected to the control plane, kept fresh by
// polling. Backs the fleet-management pane.
export function useAgents() {
  const { reeApi } = useApiRuntime();
  return useQuery({
    queryKey: queryKeys.agents(),
    queryFn: async (): Promise<Agent[]> => {
      const wire = await reeApi.listAgents();
      return sortAgents(wire.agents.map(mapAgent));
    },
    refetchInterval: AGENTS_REFETCH_MS,
  });
}
