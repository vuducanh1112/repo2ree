import type { ApiClient } from "./client";
import { endpoints } from "./endpoints";
import type {
  ApiListResponse,
  CreateWorkspaceRequestDto,
  PatchWorkspaceRequestDto,
  SourceAcquireRequestDto,
  UploadInitRequestDto,
  UploadInitResponseDto,
  WorkspaceDetailDto,
  WorkspaceSummaryDto,
} from "./types";

export interface ListWorkspacesQuery {
  cursor?: string;
  limit?: number;
  status?: string;
}

export interface WorkspaceFilesQuery {
  path?: string;
  recursive?: boolean;
  scope?: "source" | "generated" | "all";
}

export interface WorkspaceFileContentResponse {
  content: string;
  etag?: string;
  updatedAt?: string;
}

export interface PutWorkspaceFileContentRequest {
  path: string;
  content: string;
  ifMatch?: string;
}

export class WorkspaceApi {
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

  async createWorkspace(payload: CreateWorkspaceRequestDto): Promise<WorkspaceDetailDto> {
    return this.client.request<WorkspaceDetailDto>(endpoints.workspaces(), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listWorkspaces(
    query: ListWorkspacesQuery = {},
  ): Promise<ApiListResponse<WorkspaceSummaryDto>> {
    const searchParams = new URLSearchParams();
    if (query.cursor) searchParams.set("cursor", query.cursor);
    if (typeof query.limit === "number") searchParams.set("limit", String(query.limit));
    if (query.status) searchParams.set("status", query.status);
    return this.client.request<ApiListResponse<WorkspaceSummaryDto>>(
      endpoints.workspaces(),
      { method: "GET" },
      searchParams,
    );
  }

  async getWorkspace(workspaceId: string): Promise<WorkspaceDetailDto> {
    return this.client.request<WorkspaceDetailDto>(endpoints.workspace(workspaceId), {
      method: "GET",
    });
  }

  async patchWorkspace(
    workspaceId: string,
    payload: PatchWorkspaceRequestDto,
  ): Promise<WorkspaceDetailDto> {
    return this.client.request<WorkspaceDetailDto>(endpoints.workspace(workspaceId), {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteWorkspace(workspaceId: string): Promise<{ deletedAt: string; state: string }> {
    return this.client.request<{ deletedAt: string; state: string }>(
      endpoints.workspace(workspaceId),
      {
        method: "DELETE",
      },
    );
  }

  async acquireSource(
    workspaceId: string,
    payload: SourceAcquireRequestDto,
  ): Promise<{ runId: string; status: string }> {
    return this.client.request<{ runId: string; status: string }>(
      endpoints.workspaceSourceAcquire(workspaceId),
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async initUpload(
    workspaceId: string,
    payload: UploadInitRequestDto,
  ): Promise<UploadInitResponseDto> {
    return this.client.request<UploadInitResponseDto>(
      endpoints.workspaceSourceUploadInit(workspaceId),
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async completeUpload(
    workspaceId: string,
    uploadToken: string,
    archiveName: string,
  ): Promise<{ sourceSnapshotId: string; status: string }> {
    return this.client.request<{ sourceSnapshotId: string; status: string }>(
      endpoints.workspaceSourceUploadComplete(workspaceId),
      {
        method: "POST",
        body: JSON.stringify({ uploadToken, archiveName }),
      },
    );
  }

  async removeSource(workspaceId: string): Promise<{ invalidatedSteps: string[] }> {
    return this.client.request<{ invalidatedSteps: string[] }>(
      endpoints.workspaceSource(workspaceId),
      {
        method: "DELETE",
      },
    );
  }

  async getFiles(
    workspaceId: string,
    query: WorkspaceFilesQuery = {},
  ): Promise<{ nodes: Array<{ path: string; kind: string }> }> {
    const searchParams = new URLSearchParams();
    if (query.path) searchParams.set("path", query.path);
    if (typeof query.recursive === "boolean")
      searchParams.set("recursive", String(query.recursive));
    if (query.scope) searchParams.set("scope", query.scope);
    return this.client.request<{ nodes: Array<{ path: string; kind: string }> }>(
      endpoints.workspaceFiles(workspaceId),
      { method: "GET" },
      searchParams,
    );
  }

  async getFileContent(workspaceId: string, path: string): Promise<WorkspaceFileContentResponse> {
    const searchParams = new URLSearchParams({ path });
    return this.client.request<WorkspaceFileContentResponse>(
      endpoints.workspaceFileContent(workspaceId),
      { method: "GET" },
      searchParams,
    );
  }

  async putFileContent(
    workspaceId: string,
    payload: PutWorkspaceFileContentRequest,
  ): Promise<{ etag?: string; updatedAt?: string }> {
    return this.client.request<{ etag?: string; updatedAt?: string }>(
      endpoints.workspaceFileContent(workspaceId),
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  }

  async deleteFileContent(workspaceId: string, path: string): Promise<{ deletedAt?: string }> {
    const searchParams = new URLSearchParams({ path });
    return this.client.request<{ deletedAt?: string }>(
      endpoints.workspaceFileContent(workspaceId),
      {
        method: "DELETE",
      },
      searchParams,
    );
  }
}
