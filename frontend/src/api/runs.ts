import type { ApiClient } from "./client";
import { endpoints } from "./endpoints";
import type {
  ApiListResponse,
  CreateActivationTestRunRequestDto,
  CreateBuildRuntimeRunRequestDto,
  CreateEvaluateRunRequestDto,
  CreateGenerateSbomRunRequestDto,
  WorkflowLogEntryDto,
  WorkflowLogsDto,
  WorkflowRunDto,
  WorkflowRunStatusDto,
} from "./types";

interface ListRunsQuery {
  operation?: string;
  status?: WorkflowRunStatusDto;
  cursor?: string;
  limit?: number;
}

interface ListRunLogsQuery {
  cursor?: string;
  limit?: number;
  sinceTs?: string;
}

export class WorkflowRunsApi {
  constructor(private readonly client: ApiClient) {}

  async createBuildRuntimeRun(
    workspaceId: string,
    payload: CreateBuildRuntimeRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.workspaceBuildRuntime(workspaceId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateSbomRun(
    workspaceId: string,
    payload: CreateGenerateSbomRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.workspaceGenerateSbom(workspaceId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createActivationTestRun(
    workspaceId: string,
    payload: CreateActivationTestRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.workspaceActivationTest(workspaceId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createEvaluateRun(
    workspaceId: string,
    payload: CreateEvaluateRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.workspaceEvaluate(workspaceId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listRuns(
    workspaceId: string,
    query: ListRunsQuery = {},
  ): Promise<ApiListResponse<WorkflowRunDto>> {
    const searchParams = new URLSearchParams();
    if (query.operation) searchParams.set("operation", query.operation);
    if (query.status) searchParams.set("status", query.status);
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    return this.client.request<ApiListResponse<WorkflowRunDto>>(
      endpoints.workspaceRuns(workspaceId),
      { method: "GET" },
      searchParams,
    );
  }

  async getRun(workspaceId: string, runId: string): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.workspaceRun(workspaceId, runId), {
      method: "GET",
    });
  }

  async cancelRun(workspaceId: string, runId: string): Promise<{ status: WorkflowRunStatusDto }> {
    return this.client.request<{ status: WorkflowRunStatusDto }>(
      endpoints.workspaceRunCancel(workspaceId, runId),
      { method: "POST" },
    );
  }

  async retryRun(workspaceId: string, runId: string): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.workspaceRunRetry(workspaceId, runId), {
      method: "POST",
    });
  }

  async listRunLogs(
    workspaceId: string,
    runId: string,
    query: ListRunLogsQuery = {},
  ): Promise<WorkflowLogsDto> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.sinceTs) searchParams.set("sinceTs", query.sinceTs);
    return this.client.request<WorkflowLogsDto>(
      endpoints.workspaceRunLogs(workspaceId, runId),
      { method: "GET" },
      searchParams,
    );
  }
}

export function mapRunLogsToLegacy(
  lines: WorkflowLogEntryDto[],
): Array<{ type: "info" | "ok" | "warn" | "err" | "out"; msg: string; ts?: string }> {
  return lines.map((line) => {
    if (line.level === "error") {
      return { type: "err", msg: line.message, ts: line.ts };
    }
    if (line.level === "warn") {
      return { type: "warn", msg: line.message, ts: line.ts };
    }
    if (line.stream === "stdout") {
      return { type: "out", msg: line.message, ts: line.ts };
    }
    if (line.level === "debug") {
      return { type: "info", msg: line.message, ts: line.ts };
    }
    return { type: "ok", msg: line.message, ts: line.ts };
  });
}
