import type { ApiClient } from "./ApiClient";
import type {
  CreateActivationTestRunPayload,
  CreateBuildRuntimeRunPayload,
  CreateCrossCheckSbomRunPayload,
  CreateEvaluateRunPayload,
  CreateExperimentRunPayload,
  CreateGenerateHbomRunPayload,
  CreateGenerateSbomRunPayload,
  RunList,
  RunLogEntry,
  RunLogPage,
  RunStatus,
  RunSummary,
} from "./apiTypes";
import { endpoints } from "./endpoints";

interface ListRunLogsQuery {
  cursor?: string;
  limit?: number;
  sinceTs?: string;
}

export class ReeRunsApi {
  constructor(private readonly client: ApiClient) {}

  async createBuildRuntimeRun(
    reeId: string,
    payload: CreateBuildRuntimeRunPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeBuildRuntime(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateSbomRun(
    reeId: string,
    payload: CreateGenerateSbomRunPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeGenerateSbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createCrossCheckSbomRun(
    reeId: string,
    payload: CreateCrossCheckSbomRunPayload = {},
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeCrossCheckSbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateHbomRun(
    reeId: string,
    payload: CreateGenerateHbomRunPayload = {},
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeGenerateHbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createActivationTestRun(
    reeId: string,
    payload: CreateActivationTestRunPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeActivationTest(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createEvaluateRun(reeId: string, payload: CreateEvaluateRunPayload): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeEvaluate(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createExperimentRun(
    reeId: string,
    experimentName: string,
    payload: CreateExperimentRunPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeExperimentRun(reeId, experimentName), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listRuns(reeId: string): Promise<RunList> {
    return this.client.request<RunList>(endpoints.reeRuns(reeId), {
      method: "GET",
    });
  }

  async getRun(reeId: string, runId: string): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeRun(reeId, runId), {
      method: "GET",
    });
  }

  async cancelRun(reeId: string, runId: string): Promise<{ status: RunStatus }> {
    return this.client.request<{ status: RunStatus }>(endpoints.reeRunCancel(reeId, runId), {
      method: "POST",
    });
  }

  async listRunLogs(
    reeId: string,
    runId: string,
    query: ListRunLogsQuery = {},
  ): Promise<RunLogPage> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.sinceTs) searchParams.set("sinceTs", query.sinceTs);
    return this.client.request<RunLogPage>(
      endpoints.reeRunLogs(reeId, runId),
      { method: "GET" },
      searchParams,
    );
  }
}

export function mapRunLogsToLines(lines: RunLogEntry[]): Array<{
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
  ts?: string;
  stream?: "stdout" | "stderr" | "system";
}> {
  return lines.map((line) => {
    if (line.level === "error") {
      return { type: "err", msg: line.message, ts: line.ts, stream: line.stream };
    }
    if (line.level === "warn") {
      return { type: "warn", msg: line.message, ts: line.ts, stream: line.stream };
    }
    if (line.stream === "stdout") {
      return { type: "out", msg: line.message, ts: line.ts, stream: line.stream };
    }
    if (line.level === "debug") {
      return { type: "info", msg: line.message, ts: line.ts, stream: line.stream };
    }
    return { type: "ok", msg: line.message, ts: line.ts, stream: line.stream };
  });
}
