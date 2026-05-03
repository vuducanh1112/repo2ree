import { useMemo } from "react";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceResetPayload } from "../../domain/workspace/WorkspaceReset";
import type { ReeProject, WorkspaceBinaryDownload } from "../../domain/workspace/WorkspaceTypes";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { ensureWorkspaceId } from "../client";
import { mapWorkspaceDetailToReeProject } from "./workspaceMapping";

export interface WorkspaceClient<TFile = unknown> {
  getWorkspace(id: string): Promise<ReeProject<TFile>>;
  updateFile(id: string, path: string, content: string): Promise<void>;
  updateReeDraft(id: string, reePatch: Record<string, unknown>): Promise<void>;
  deleteFile(id: string, path: string): Promise<void>;
  getFileBytes(id: string, path: string): Promise<ArrayBuffer>;
  getReeArchive(id: string): Promise<WorkspaceBinaryDownload>;
  resetWorkspaceRequest(id: string, request: WorkspaceResetPayload): Promise<void>;
}

function createWorkspaceClient(runtime: ApiRuntimeValue): WorkspaceClient<FileTreeNode> {
  return {
    async getWorkspace(id) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      const workspace = await runtime.workspaceApi.getWorkspace(workspaceId);
      return mapWorkspaceDetailToReeProject(workspace);
    },
    async updateFile(id, path, content) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      await runtime.workspaceApi.putFileContent(workspaceId, { path, content });
    },
    async updateReeDraft(id, reePatch) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      await runtime.workspaceApi.patchWorkspace(workspaceId, { reePatch });
    },
    async deleteFile(id, path) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      await runtime.workspaceApi.deleteFileContent(workspaceId, path);
    },
    async getFileBytes(id, path) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      return runtime.workspaceApi.getFileBytes(workspaceId, path);
    },
    async getReeArchive(id) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      return runtime.workspaceApi.getReeArchive(workspaceId);
    },
    async resetWorkspaceRequest(id, request) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      const mode = request.mode || "clear";
      if (mode === "clear") {
        await runtime.workspaceApi.removeSource(workspaceId);
        return;
      }
      if (mode === "download") {
        await runtime.workspaceApi.acquireSource(workspaceId, {
          originUrl: String(request.source ?? ""),
          sourceType: String(request.sourceType ?? "git") as "git" | "tarball" | "zip",
        });
        return;
      }
      if (mode === "upload") {
        const archiveName = String(request.archiveName || "source.tar.gz");
        const init = await runtime.workspaceApi.initUpload(workspaceId, {
          fileName: archiveName,
          size: 0,
          contentType: "application/gzip",
        });
        if (request.archiveContentBase64) {
          const archiveData = decodeBase64ToArrayBuffer(String(request.archiveContentBase64));
          await runtime.workspaceApi.uploadSourceBytes(init.uploadUrl, archiveData);
        }
        await runtime.workspaceApi.completeUpload(workspaceId, init.uploadToken, archiveName);
        return;
      }
      throw new Error(`Unsupported workspace reset mode: ${mode}`);
    },
  };
}

export function useWorkspaceClient(): WorkspaceClient<FileTreeNode> {
  const runtime = useApiRuntime();
  return useMemo(() => createWorkspaceClient(runtime), [runtime]);
}

function decodeBase64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}
