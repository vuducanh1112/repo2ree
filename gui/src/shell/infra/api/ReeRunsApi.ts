import type { ApiClient } from "./ApiClient";
import type {
  ActivateExperimentEnvironmentPayload,
  BuildExperimentEnvironmentPayload,
  CrossCheckSbomPayload,
  EvaluateReproducibilityPayload,
  GenerateSbomPayload,
  ObserveHardwarePayload,
  RunExperimentPayload,
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

  async buildExperimentEnvironment(
    reeId: string,
    payload: BuildExperimentEnvironmentPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.buildExperimentEnvironment(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async generateSbom(reeId: string, payload: GenerateSbomPayload): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.generateSbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async crossCheckSbom(reeId: string, payload: CrossCheckSbomPayload = {}): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.crossCheckSbom(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async observeHardware(reeId: string, payload: ObserveHardwarePayload = {}): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.observeHardware(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async activateExperimentEnvironment(
    reeId: string,
    payload: ActivateExperimentEnvironmentPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.activateExperimentEnvironment(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async evaluateReproducibility(
    reeId: string,
    payload: EvaluateReproducibilityPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.evaluateReproducibility(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async runExperiment(
    reeId: string,
    experimentName: string,
    payload: RunExperimentPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.runExperiment(reeId, experimentName), {
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

const REPORTS_ERROR = /\bERROR\b|(^|\s)(error|fatal):/;

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
    if (line.stream === "stderr" && REPORTS_ERROR.test(line.message)) {
      return { type: "err", msg: line.message, ts: line.ts, stream: line.stream };
    }
    if (line.stream === "stdout" || line.stream === "stderr") {
      return { type: "out", msg: line.message, ts: line.ts, stream: line.stream };
    }
    if (line.level === "warn") {
      return { type: "warn", msg: line.message, ts: line.ts, stream: line.stream };
    }
    if (line.level === "debug") {
      return { type: "info", msg: line.message, ts: line.ts, stream: line.stream };
    }
    return { type: "ok", msg: line.message, ts: line.ts, stream: line.stream };
  });
}
