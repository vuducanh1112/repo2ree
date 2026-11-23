import type { ReeId } from "@core/ree/ReeId";
import type { ApiClient } from "./ApiClient";
import type {
  AcquireSourcePayload,
  ApiListResponse,
  BuildInfo,
  DeleteReeResponse,
  FileMutationResponse,
  InferenceReport,
  LintReport,
  LintScriptsResponse,
  OperationHistoryWire,
  PatchReeDefinitionPayload,
  ReeCreatePayload,
  ReeDocument,
  ReeIndexList,
  ReeState,
  ReeSummary,
  ReproducibilityReportWire,
  ReviewAcquireSourcePayload,
  ReviewBuildExperimentEnvironmentPayload,
  ReviewSetWire,
  RunSummary,
  ScriptDeclarations,
  ScriptTargetSelector,
  ScriptTemplateCatalog,
  StoreList,
  UploadInitPayload,
  UploadInitResponse,
  WorkbenchList,
} from "./apiTypes";
import { endpoints } from "./endpoints";

interface ListReesQuery {
  cursor?: string;
  limit?: number;
  status?: string;
}

interface ListReeIndexQuery {
  cursor?: string;
  limit?: number;
  depositedOnly?: boolean;
}

interface PutReeFileContentRequest {
  path: string;
  content: string;
  if_match?: string;
}

function parseContentDispositionFilename(contentDisposition: string | null): string | undefined {
  if (!contentDisposition) return undefined;
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].trim());
    } catch {
      return utf8Match[1].trim();
    }
  }
  const quoted = contentDisposition.match(/filename="([^"]+)"/i);
  if (quoted?.[1]) return quoted[1].trim();
  const plain = contentDisposition.match(/filename=([^;]+)/i);
  return plain?.[1]?.trim();
}

export class ReeApi {
  constructor(private readonly client: ApiClient) {}

  async getBuildInfo(): Promise<BuildInfo> {
    return this.client.request<BuildInfo>(endpoints.buildInfo(), { method: "GET" });
  }

  async listStores(): Promise<StoreList> {
    return this.client.request<StoreList>(endpoints.stores(), { method: "GET" });
  }

  async listScriptTemplates(reeId: ReeId | string): Promise<ScriptTemplateCatalog> {
    return this.client.request<ScriptTemplateCatalog>(endpoints.reeScriptTemplates(reeId), {
      method: "GET",
    });
  }

  async listWorkbenches(): Promise<WorkbenchList> {
    return this.client.request<WorkbenchList>(endpoints.workbenches(), { method: "GET" });
  }

  async listReeIndex(query: ListReeIndexQuery = {}): Promise<ReeIndexList> {
    const search = new URLSearchParams();
    if (query.cursor) {
      search.set("cursor", query.cursor);
    }
    if (query.limit !== undefined) {
      search.set("limit", String(query.limit));
    }
    if (query.depositedOnly) {
      search.set("deposited_only", "true");
    }
    const qs = search.toString();
    return this.client.request<ReeIndexList>(`${endpoints.reeIndex()}${qs ? `?${qs}` : ""}`, {
      method: "GET",
    });
  }

  async uploadStagedBytes(uploadUrl: string, data: ArrayBuffer): Promise<void> {
    await this.client.request<Record<string, unknown>>(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": "application/octet-stream",
      },
      body: data,
    });
  }

  async createRee(payload: ReeCreatePayload): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.rees(), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listRees(query: ListReesQuery = {}): Promise<ApiListResponse<ReeSummary>> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.status) searchParams.set("status", query.status);
    return this.client.request<ApiListResponse<ReeSummary>>(
      endpoints.rees(),
      { method: "GET" },
      searchParams,
    );
  }

  async getRee(reeId: ReeId, signal?: AbortSignal): Promise<ReeDocument> {
    return this.client.request<ReeDocument>(endpoints.ree(reeId), { method: "GET", signal });
  }

  async getReeState(reeId: ReeId): Promise<ReeState> {
    return this.client.request<ReeState>(endpoints.reeState(reeId), { method: "GET" });
  }

  async getReproducibilityReport(reeId: ReeId): Promise<ReproducibilityReportWire> {
    return this.client.request<ReproducibilityReportWire>(endpoints.reproducibilityReport(reeId), {
      method: "GET",
    });
  }

  async listOperationHistory(reeId: ReeId | string): Promise<OperationHistoryWire> {
    return this.client.request<OperationHistoryWire>(endpoints.operationHistory(reeId), {
      method: "GET",
    });
  }

  async listReviews(reeId: ReeId | string): Promise<ReviewSetWire> {
    return this.client.request<ReviewSetWire>(endpoints.reeReviews(reeId), { method: "GET" });
  }

  async reviewAcquireSource(
    reeId: ReeId | string,
    payload: ReviewAcquireSourcePayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reviewAcquireSource(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async reviewBuildExperimentEnvironment(
    reeId: ReeId | string,
    reviewId: string,
    payload: ReviewBuildExperimentEnvironmentPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(
      endpoints.reviewBuildExperimentEnvironment(reeId, reviewId),
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async reviewRunExperiment(
    reeId: ReeId | string,
    reviewId: string,
    experimentName: string,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(
      endpoints.reviewRunExperiment(reeId, reviewId, experimentName),
      { method: "POST", body: JSON.stringify({}) },
    );
  }

  async reviewActivateExperimentEnvironment(
    reeId: ReeId | string,
    reviewId: string,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(
      endpoints.reviewActivateExperimentEnvironment(reeId, reviewId),
      {
        method: "POST",
        body: JSON.stringify({}),
      },
    );
  }

  async patchReeDefinition(reeId: ReeId, payload: PatchReeDefinitionPayload): Promise<ReeDocument> {
    return this.client.request<ReeDocument>(endpoints.patchReeDefinition(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async deleteRee(reeId: ReeId): Promise<DeleteReeResponse> {
    return this.client.request<DeleteReeResponse>(endpoints.ree(reeId), {
      method: "DELETE",
    });
  }

  async acquireSource(reeId: ReeId, payload: AcquireSourcePayload): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.acquireSource(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async initUpload(reeId: ReeId, payload: UploadInitPayload): Promise<UploadInitResponse> {
    return this.client.request<UploadInitResponse>(endpoints.reeSourceUploadInit(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async completeUpload(
    reeId: ReeId,
    uploadToken: string,
    archiveName: string,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeSourceUploadComplete(reeId), {
      method: "POST",
      body: JSON.stringify({ upload_token: uploadToken, archive_name: archiveName }),
    });
  }

  async initBundleUpload(reeId: ReeId, payload: UploadInitPayload): Promise<UploadInitResponse> {
    return this.client.request<UploadInitResponse>(endpoints.reeBundleUploadInit(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async loadReeBundle(reeId: ReeId, uploadToken: string, archiveName: string): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.loadReeBundle(reeId), {
      method: "POST",
      body: JSON.stringify({ upload_token: uploadToken, archive_name: archiveName }),
    });
  }

  async removeSource(reeId: ReeId): Promise<void> {
    await this.client.request<unknown>(endpoints.removeSource(reeId), {
      method: "POST",
    });
  }

  async getReeFileBytes(reeId: ReeId, path: string): Promise<ArrayBuffer> {
    const searchParams = new URLSearchParams({ path });
    return this.client.requestArrayBuffer(
      endpoints.reeFileRaw(reeId),
      { method: "GET" },
      searchParams,
    );
  }

  async sealRee(
    reeId: ReeId,
    opts: {
      includeSource: boolean;
      includeExperimentEnvironment: boolean;
      includeResults: boolean;
    },
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.sealRee(reeId), {
      method: "POST",
      body: JSON.stringify({
        include_source: opts.includeSource,
        include_experiment_environment: opts.includeExperimentEnvironment,
        include_results: opts.includeResults,
      }),
    });
  }

  async getReeArchive(reeId: ReeId): Promise<{ bytes: ArrayBuffer; fileName?: string }> {
    const response = await this.client.requestArrayBufferWithMeta(endpoints.reeArchive(reeId), {
      method: "GET",
    });
    return {
      bytes: response.bytes,
      fileName: parseContentDispositionFilename(response.headers.get("content-disposition")),
    };
  }

  async writeScript(
    reeId: ReeId,
    payload: PutReeFileContentRequest,
  ): Promise<FileMutationResponse> {
    return this.client.request<FileMutationResponse>(endpoints.writeScript(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async suggestScripts(
    reeId: ReeId | string,
    targets: ScriptTargetSelector[],
  ): Promise<InferenceReport> {
    return this.client.request<InferenceReport>(endpoints.suggestScripts(reeId), {
      method: "POST",
      body: JSON.stringify({ targets }),
    });
  }

  async lintScripts(
    reeId: ReeId | string,
    targets: ScriptTargetSelector[],
  ): Promise<LintScriptsResponse> {
    return this.client.request<LintScriptsResponse>(endpoints.lintScripts(reeId), {
      method: "POST",
      body: JSON.stringify({ targets }),
    });
  }

  async checkScriptDraft(
    reeId: ReeId | string,
    target: ScriptTargetSelector,
    source: string,
    declarations: ScriptDeclarations,
  ): Promise<LintReport> {
    return this.client.request<LintReport>(endpoints.reeScriptLintDraft(reeId), {
      method: "POST",
      body: JSON.stringify({ target, source, declarations }),
    });
  }
}
