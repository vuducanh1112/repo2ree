import type { ApiClient } from "./ApiClient";
import type {
  CreateActivationTestRunRequestDto,
  CreateBuildRuntimeRunRequestDto,
  CreateEvaluateRunRequestDto,
  CreateGenerateHbomRunRequestDto,
  CreateGenerateSbomRunRequestDto,
  WorkflowLogEntryDto,
  WorkflowLogsDto,
  WorkflowRunDto,
  WorkflowRunStatusDto,
} from "./apiTypes";
import { endpoints } from "./endpoints";

interface ListRunLogsQuery {
  cursor?: string;
  limit?: number;
  sinceTs?: string;
}

export class ExecutionRunsApi {
  constructor(private readonly client: ApiClient) {}

  async createBuildRuntimeRun(
    reeId: string,
    payload: CreateBuildRuntimeRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeBuildRuntime(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateSbomRun(
    reeId: string,
    payload: CreateGenerateSbomRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeGenerateSbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateHbomRun(
    reeId: string,
    payload: CreateGenerateHbomRunRequestDto = {},
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeGenerateHbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createActivationTestRun(
    reeId: string,
    payload: CreateActivationTestRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeActivationTest(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createEvaluateRun(
    reeId: string,
    payload: CreateEvaluateRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeEvaluate(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getRun(reeId: string, runId: string): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeRun(reeId, runId), {
      method: "GET",
    });
  }

  async cancelRun(reeId: string, runId: string): Promise<{ status: WorkflowRunStatusDto }> {
    return this.client.request<{ status: WorkflowRunStatusDto }>(
      endpoints.reeRunCancel(reeId, runId),
      { method: "POST" },
    );
  }

  async listRunLogs(
    reeId: string,
    runId: string,
    query: ListRunLogsQuery = {},
  ): Promise<WorkflowLogsDto> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.sinceTs) searchParams.set("sinceTs", query.sinceTs);
    return this.client.request<WorkflowLogsDto>(
      endpoints.reeRunLogs(reeId, runId),
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
