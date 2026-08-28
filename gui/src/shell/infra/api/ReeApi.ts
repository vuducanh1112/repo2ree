import type { ReeId } from "@core/ree/ReeId";
import type { ApiClient } from "./ApiClient";
import type {
  AgentList,
  ApiListResponse,
  CreateBuildReviewPayload,
  CreateSourceReviewPayload,
  DeleteReeResponse,
  FileMutationResponse,
  InferenceReport,
  LintReport,
  LintScriptsResponse,
  ReeCreatePayload,
  ReeDefinitionPatchPayload,
  ReeDocument,
  ReeIndexList,
  ReeStepCatalog,
  ReeSummary,
  ReproducibilityReportWire,
  ReprovisionResponse,
  ReviewSetWire,
  RunSummary,
  ScriptDeclarations,
  ScriptTargetSelector,
  ScriptTemplateCatalog,
  SourceAcquirePayload,
  UploadInitPayload,
  UploadInitResponse,
  WorkbenchImageCatalog,
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
  /** Narrow to entries some archive has issued an identifier for. */
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

  /** Ordered authoring steps and their prerequisite edges. */
  async listReeSteps(): Promise<ReeStepCatalog> {
    return this.client.request<ReeStepCatalog>(endpoints.reeSteps(), { method: "GET" });
  }

  /** The base images the backend offers at provision time. */
  async listWorkbenchImages(): Promise<WorkbenchImageCatalog> {
    return this.client.request<WorkbenchImageCatalog>(endpoints.workbenchImages(), {
      method: "GET",
    });
  }

  /** Backend-owned starter templates for the REE-owned scripts. */
  async listScriptTemplates(): Promise<ScriptTemplateCatalog> {
    return this.client.request<ScriptTemplateCatalog>(endpoints.scriptTemplates(), {
      method: "GET",
    });
  }

  /** Workbench agents currently dialed into the control plane. */
  async listAgents(): Promise<AgentList> {
    return this.client.request<AgentList>(endpoints.agents(), { method: "GET" });
  }

  /**
   * REEs sealed on this control plane, newest first.
   *
   * Not REE-scoped and not tied to a live workbench: entries outlive the
   * benches they were authored in, which is the point of the index.
   */
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

  /**
   * Provisioning runs in the background so the workbench image pull streams its
   * progress live — the response is the provisioning run (carrying reeId +
   * runId), not the finished workspace. Poll the run / its log feed and fetch
   * the workspace with {@link getRee} once it reaches "succeeded".
   */
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

  async getRee(reeId: ReeId): Promise<ReeDocument> {
    return this.client.request<ReeDocument>(endpoints.ree(reeId), {
      method: "GET",
    });
  }

  async getEvaluateReport(reeId: ReeId): Promise<ReproducibilityReportWire> {
    return this.client.request<ReproducibilityReportWire>(endpoints.reeEvaluateReport(reeId), {
      method: "GET",
    });
  }

  async listReviews(reeId: ReeId | string): Promise<ReviewSetWire> {
    return this.client.request<ReviewSetWire>(endpoints.reeReviews(reeId), { method: "GET" });
  }

  async startSourceReview(
    reeId: ReeId | string,
    payload: CreateSourceReviewPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeSourceReview(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async startBuildReview(
    reeId: ReeId | string,
    reviewId: string,
    payload: CreateBuildReviewPayload,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeBuildReview(reeId, reviewId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  /**
   * Probe whether the runtime an attempt certified is inhabitable. Takes no
   * basis, unlike the two steps before it: activation inherits what the
   * attempt's evidence is worth rather than choosing.
   */
  /**
   * Reproduce one experiment's result inside an attempt whose runtime came up.
   * One name per call, like the author's own experiment route: reproducing the
   * whole set is this called in sequence, so each run keeps its own log,
   * receipt, and cancel point.
   */
  async startExperimentReview(
    reeId: ReeId | string,
    reviewId: string,
    experimentName: string,
  ): Promise<RunSummary> {
    return this.client.request<RunSummary>(
      endpoints.reeExperimentReview(reeId, reviewId, experimentName),
      { method: "POST", body: JSON.stringify({}) },
    );
  }

  async startActivationReview(reeId: ReeId | string, reviewId: string): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeActivationReview(reeId, reviewId), {
      method: "POST",
      body: JSON.stringify({}),
    });
  }

  async patchReeDefinition(reeId: ReeId, payload: ReeDefinitionPatchPayload): Promise<ReeDocument> {
    return this.client.request<ReeDocument>(endpoints.reeDefinition(reeId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteRee(reeId: ReeId): Promise<DeleteReeResponse> {
    return this.client.request<DeleteReeResponse>(endpoints.ree(reeId), {
      method: "DELETE",
    });
  }

  async acquireSource(reeId: ReeId, payload: SourceAcquirePayload): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeSourceAcquire(reeId), {
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

  /** Open a staging slot for a downloaded REE bundle (the `ree:load` counterpart of `initUpload`). */
  async initBundleUpload(reeId: ReeId, payload: UploadInitPayload): Promise<UploadInitResponse> {
    return this.client.request<UploadInitResponse>(endpoints.reeBundleUploadInit(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  /** Make the REE be the staged bundle: intent, source, and author evidence. */
  async loadReeBundle(reeId: ReeId, uploadToken: string, archiveName: string): Promise<RunSummary> {
    return this.client.request<RunSummary>(endpoints.reeBundleLoad(reeId), {
      method: "POST",
      body: JSON.stringify({ upload_token: uploadToken, archive_name: archiveName }),
    });
  }

  async removeSource(reeId: ReeId): Promise<void> {
    await this.client.request<unknown>(endpoints.reeSource(reeId), {
      method: "DELETE",
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
    opts: { includeSource: boolean; includeRuntime: boolean; includeResults: boolean },
  ): Promise<ReeDocument> {
    return this.client.request<ReeDocument>(endpoints.reeSeal(reeId), {
      method: "POST",
      body: JSON.stringify({
        include_source: opts.includeSource,
        include_runtime: opts.includeRuntime,
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

  async putFileContent(
    reeId: ReeId,
    payload: PutReeFileContentRequest,
  ): Promise<FileMutationResponse> {
    return this.client.request<FileMutationResponse>(endpoints.reeFileContent(reeId), {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  }

  /**
   * Read-only inference of the REE-owned scripts for the requested targets.
   * Recomputed on every call and persists nothing; the returned candidate
   * bytes become a script only when the caller writes them via
   * {@link putFileContent}.
   */
  async generateScriptCandidates(
    reeId: ReeId | string,
    targets: ScriptTargetSelector[],
  ): Promise<InferenceReport> {
    return this.client.request<InferenceReport>(endpoints.reeScriptInferences(reeId), {
      method: "POST",
      body: JSON.stringify({ targets }),
    });
  }

  /**
   * Static checks over the REE's written scripts, on every tier the bench can
   * run. Read-only and always recomputed; a target with no script yet comes
   * back under `missing_scripts` rather than as an empty report.
   */
  async lintReeScripts(
    reeId: ReeId | string,
    targets: ScriptTargetSelector[],
  ): Promise<LintScriptsResponse> {
    return this.client.request<LintScriptsResponse>(endpoints.reeScriptLints(reeId), {
      method: "POST",
      body: JSON.stringify({ targets }),
    });
  }

  /**
   * Static checks over a script that has not been saved — the bytes in an
   * editor, with the declarations to grade them against. Stateless and not
   * REE-scoped: it reads nothing, writes nothing, and needs no workbench, which
   * is what lets an editor call it while the author types. Contract tier only;
   * the syntax and shell tiers need a process and live on {@link lintReeScripts}.
   */
  async checkScriptDraft(
    target: ScriptTargetSelector,
    source: string,
    declarations: ScriptDeclarations,
  ): Promise<LintReport> {
    return this.client.request<LintReport>(endpoints.scriptLintDraft(), {
      method: "POST",
      body: JSON.stringify({ target, source, declarations }),
    });
  }

  async reprovisionWorkbench(reeId: ReeId | string): Promise<ReprovisionResponse> {
    return this.client.request<ReprovisionResponse>(endpoints.reeWorkbenchReprovision(reeId), {
      method: "POST",
    });
  }

  async deleteFileContent(reeId: ReeId, path: string): Promise<FileMutationResponse> {
    const searchParams = new URLSearchParams({ path });
    return this.client.request<FileMutationResponse>(
      endpoints.reeFileContent(reeId),
      {
        method: "DELETE",
      },
      searchParams,
    );
  }
}
