import type { Agent } from "@core/agent/Agent";
import { sortAgents } from "@core/agent/Agent";
import type { AgentSummaryDto } from "@shell/infra/api/apiTypes";
import { useQuery } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// Pure DTO → domain map. Status is narrowed to the domain's single connected
// state; the endpoint only lists connected agents.
function mapAgent(dto: AgentSummaryDto): Agent {
  return {
    id: dto.agent_id,
    hostname: dto.hostname,
    version: dto.version,
    dockerMode: dto.docker_mode,
    connectedAt: dto.connected_at,
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
      const dto = await reeApi.listAgents();
      return sortAgents(dto.agents.map(mapAgent));
    },
    refetchInterval: AGENTS_REFETCH_MS,
  });
}
