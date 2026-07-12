import type { ApiClient } from "./ApiClient";
import type {
  CreateActivationTestRunRequestDto,
  CreateBuildRuntimeRunRequestDto,
  CreateEvaluateRunRequestDto,
  CreateExperimentRunRequestDto,
  CreateGenerateHbomRunRequestDto,
  CreateGenerateSbomRunRequestDto,
  ReeRunDto,
  ReeRunLogEntryDto,
  ReeRunLogsDto,
  ReeRunStatusDto,
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
    payload: CreateBuildRuntimeRunRequestDto,
  ): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeBuildRuntime(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateSbomRun(
    reeId: string,
    payload: CreateGenerateSbomRunRequestDto,
  ): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeGenerateSbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createGenerateHbomRun(
    reeId: string,
    payload: CreateGenerateHbomRunRequestDto = {},
  ): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeGenerateHbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createActivationTestRun(
    reeId: string,
    payload: CreateActivationTestRunRequestDto,
  ): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeActivationTest(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createEvaluateRun(reeId: string, payload: CreateEvaluateRunRequestDto): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeEvaluate(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createExperimentRun(
    reeId: string,
    experimentName: string,
    payload: CreateExperimentRunRequestDto,
  ): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeExperimentRun(reeId, experimentName), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getRun(reeId: string, runId: string): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeRun(reeId, runId), {
      method: "GET",
    });
  }

  async cancelRun(reeId: string, runId: string): Promise<{ status: ReeRunStatusDto }> {
    return this.client.request<{ status: ReeRunStatusDto }>(endpoints.reeRunCancel(reeId, runId), {
      method: "POST",
    });
  }

  async listRunLogs(
    reeId: string,
    runId: string,
    query: ListRunLogsQuery = {},
  ): Promise<ReeRunLogsDto> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.sinceTs) searchParams.set("sinceTs", query.sinceTs);
    return this.client.request<ReeRunLogsDto>(
      endpoints.reeRunLogs(reeId, runId),
      { method: "GET" },
      searchParams,
    );
  }
}

export function mapRunLogsToLines(
  lines: ReeRunLogEntryDto[],
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
