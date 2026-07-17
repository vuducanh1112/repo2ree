import type { ReeId } from "@core/ree/ReeId";
import type { ApiClient } from "./ApiClient";
import type {
  AgentList,
  ApiListResponse,
  DeleteReeResponse,
  FileMutationResponse,
  ReeCreatePayload,
  ReeDocument,
  ReeIntentPatchPayload,
  ReeSummary,
  ReprovisionResponse,
  RunSummary,
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

  async uploadSourceBytes(uploadUrl: string, data: ArrayBuffer): Promise<void> {
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

  async getEvaluateReport(reeId: ReeId): Promise<unknown> {
    return this.client.request<unknown>(endpoints.reeEvaluateReport(reeId), {
      method: "GET",
    });
  }

  async getScorecard(reeId: ReeId): Promise<unknown> {
    return this.client.request<unknown>(endpoints.reeScorecard(reeId), {
      method: "GET",
    });
  }

  async patchReeIntent(reeId: ReeId, payload: ReeIntentPatchPayload): Promise<ReeDocument> {
    return this.client.request<ReeDocument>(endpoints.reeIntent(reeId), {
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

  async removeSource(reeId: ReeId): Promise<void> {
    await this.client.request<unknown>(endpoints.reeSource(reeId), {
      method: "DELETE",
    });
  }

  async getFileBytes(reeId: ReeId, path: string): Promise<ArrayBuffer> {
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
