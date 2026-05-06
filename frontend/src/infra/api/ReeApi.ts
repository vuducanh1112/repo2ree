import type { ReeId } from "../../core/ree/ReeId";
import type { ApiClient } from "./ApiClient";
import type {
  ApiListResponse,
  CreateReeRequestDto,
  PatchReeRequestDto,
  ReeDetailDto,
  ReeSummaryDto,
  SourceAcquireRequestDto,
  UploadInitRequestDto,
  UploadInitResponseDto,
  WorkflowRunDto,
} from "./apiTypes";
import { endpoints } from "./endpoints";

interface ListReesQuery {
  cursor?: string;
  limit?: number;
  status?: string;
}

interface ReeFilesQuery {
  path?: string;
  recursive?: boolean;
  scope?: "source" | "generated" | "all";
}

interface ReeFileContentResponse {
  content: string;
  etag?: string;
  updatedAt?: string;
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

  async uploadSourceBytes(uploadUrl: string, data: ArrayBuffer): Promise<void> {
    await this.client.request<Record<string, unknown>>(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": "application/octet-stream",
      },
      body: data,
    });
  }

  async createRee(payload: CreateReeRequestDto): Promise<ReeDetailDto> {
    return this.client.request<ReeDetailDto>(endpoints.rees(), {
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

  async patchRee(reeId: ReeId, payload: PatchReeRequestDto): Promise<ReeDetailDto> {
    return this.client.request<ReeDetailDto>(endpoints.ree(reeId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteRee(reeId: ReeId): Promise<{ deletedAt: string; state: string }> {
    return this.client.request<{ deletedAt: string; state: string }>(endpoints.ree(reeId), {
      method: "DELETE",
    });
  }

  async acquireSource(reeId: ReeId, payload: SourceAcquireRequestDto): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeSourceAcquire(reeId), {
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

  async completeUpload(
    reeId: ReeId,
    uploadToken: string,
    archiveName: string,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reeSourceUploadComplete(reeId), {
      method: "POST",
      body: JSON.stringify({ uploadToken, archiveName }),
    });
  }

  async removeSource(reeId: ReeId): Promise<{ invalidatedSteps: string[] }> {
    return this.client.request<{ invalidatedSteps: string[] }>(endpoints.reeSource(reeId), {
      method: "DELETE",
    });
  }

  async getFiles(
    reeId: ReeId,
    query: ReeFilesQuery = {},
  ): Promise<{ nodes: Array<{ path: string; kind: string; size?: number }> }> {
    const searchParams = new URLSearchParams();
    if (query.path) searchParams.set("path", query.path);
    if (typeof query.recursive === "boolean")
      searchParams.set("recursive", String(query.recursive));
    if (query.scope) searchParams.set("scope", query.scope);
    return this.client.request<{ nodes: Array<{ path: string; kind: string; size?: number }> }>(
      endpoints.reeFiles(reeId),
      { method: "GET" },
      searchParams,
    );
  }

  async getFileBytes(reeId: ReeId, path: string): Promise<ArrayBuffer> {
    const searchParams = new URLSearchParams({ path });
    return this.client.requestArrayBuffer(
      endpoints.reeFileRaw(reeId),
      { method: "GET" },
      searchParams,
    );
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

  async getFileContent(reeId: ReeId, path: string): Promise<ReeFileContentResponse> {
    const searchParams = new URLSearchParams({ path });
    return this.client.request<ReeFileContentResponse>(
      endpoints.reeFileContent(reeId),
      { method: "GET" },
      searchParams,
    );
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
