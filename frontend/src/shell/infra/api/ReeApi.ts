import type { ReeId } from "@core/ree/ReeId";
import type { ApiClient } from "./ApiClient";
import type {
  AgentListDto,
  ApiListResponse,
  CreateReeRequestDto,
  PatchReeRequestDto,
  ReeDetailDto,
  ReeRunDto,
  ReeSummaryDto,
  SourceAcquireRequestDto,
  UploadInitRequestDto,
  UploadInitResponseDto,
  WorkbenchImageCatalogDto,
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
  ifMatch?: string;
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
  async listWorkbenchImages(): Promise<WorkbenchImageCatalogDto> {
    return this.client.request<WorkbenchImageCatalogDto>(endpoints.workbenchImages(), {
      method: "GET",
    });
  }

  /** Workbench agents currently dialed into the control plane. */
  async listAgents(): Promise<AgentListDto> {
    return this.client.request<AgentListDto>(endpoints.agents(), { method: "GET" });
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
  async createRee(payload: CreateReeRequestDto): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.rees(), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listRees(query: ListReesQuery = {}): Promise<ApiListResponse<ReeSummaryDto>> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.status) searchParams.set("status", query.status);
    return this.client.request<ApiListResponse<ReeSummaryDto>>(
      endpoints.rees(),
      { method: "GET" },
      searchParams,
    );
  }

  async getRee(reeId: ReeId): Promise<ReeDetailDto> {
    return this.client.request<ReeDetailDto>(endpoints.ree(reeId), {
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

  async patchReeIntent(reeId: ReeId, payload: PatchReeRequestDto): Promise<ReeDetailDto> {
    return this.client.request<ReeDetailDto>(endpoints.reeIntent(reeId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteRee(reeId: ReeId): Promise<{ deletedAt: string; state: string }> {
    return this.client.request<{ deletedAt: string; state: string }>(endpoints.ree(reeId), {
      method: "DELETE",
    });
  }

  async acquireSource(reeId: ReeId, payload: SourceAcquireRequestDto): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeSourceAcquire(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async initUpload(reeId: ReeId, payload: UploadInitRequestDto): Promise<UploadInitResponseDto> {
    return this.client.request<UploadInitResponseDto>(endpoints.reeSourceUploadInit(reeId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async completeUpload(reeId: ReeId, uploadToken: string, archiveName: string): Promise<ReeRunDto> {
    return this.client.request<ReeRunDto>(endpoints.reeSourceUploadComplete(reeId), {
      method: "POST",
      body: JSON.stringify({ uploadToken, archiveName }),
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
  ): Promise<ReeDetailDto> {
    return this.client.request<ReeDetailDto>(endpoints.reeSeal(reeId), {
      method: "POST",
      body: JSON.stringify({
        includeSource: opts.includeSource,
        includeRuntime: opts.includeRuntime,
        includeResults: opts.includeResults,
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
  ): Promise<{ etag?: string; updatedAt?: string }> {
    return this.client.request<{ etag?: string; updatedAt?: string }>(
      endpoints.reeFileContent(reeId),
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  }

  async reprovisionWorkbench(reeId: ReeId | string): Promise<{ status: string; reeId: string }> {
    return this.client.request<{ status: string; reeId: string }>(
      endpoints.reeWorkbenchReprovision(reeId),
      { method: "POST" },
    );
  }

  async deleteFileContent(reeId: ReeId, path: string): Promise<{ deletedAt?: string }> {
    const searchParams = new URLSearchParams({ path });
    return this.client.request<{ deletedAt?: string }>(
      endpoints.reeFileContent(reeId),
      {
        method: "DELETE",
      },
      searchParams,
    );
  }
}
