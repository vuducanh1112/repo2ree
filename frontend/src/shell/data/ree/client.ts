import type { ReeId } from "@core/ree/ReeId";
import type { ReeIntentPatch } from "@core/ree/reePatch";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { WorkspaceResetPayload } from "@core/workspace/WorkspaceReset";
import type { ReeProject, WorkspaceBinaryDownload } from "@core/workspace/WorkspaceTypes";
import { useMemo } from "react";
import { type ReeDetailDto, toSourceAcquireRequest } from "../../infra/api/apiTypes";
import type { ReeApi } from "../../infra/api/ReeApi";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { ensureReeId } from "../client";
import { mapReeDetailToReeProject } from "./reeMapping";

type ReeApiRuntime = ApiRuntimeValue & { reeApi: ReeApi };
type ReeProjectState = NonNullable<ReturnType<typeof mapReeDetailToReeProject>["ree"]>;

export interface ReeClient<TFile = unknown, TRee = unknown> {
  getRee(id: ReeId | string): Promise<ReeProject<TFile, TRee>>;
  updateFile(id: ReeId | string, path: string, content: string): Promise<void>;
  updateReeIntent(id: ReeId | string, intentPatch: ReeIntentPatch): Promise<void>;
  deleteFile(id: ReeId | string, path: string): Promise<void>;
  getFileBytes(id: ReeId | string, path: string): Promise<ArrayBuffer>;
  sealRee(
    id: ReeId | string,
    opts: { includeSource: boolean; includeRuntime: boolean },
  ): Promise<ReeDetailDto>;
  getReeArchive(id: ReeId | string): Promise<WorkspaceBinaryDownload>;
  resetWorkspaceRequest(id: ReeId | string, request: WorkspaceResetPayload): Promise<void>;
}

function createReeClient(runtime: ReeApiRuntime): ReeClient<FileTreeNode, ReeProjectState> {
  return {
    async getRee(id) {
      const reeId = await ensureReeId(runtime, id);
      const ree = await runtime.reeApi.getRee(reeId);
      return mapReeDetailToReeProject(ree);
    },
    async updateFile(id, path, content) {
      const reeId = await ensureReeId(runtime, id);
      await runtime.reeApi.putFileContent(reeId, { path, content });
    },
    async updateReeIntent(id, intentPatch) {
      const reeId = await ensureReeId(runtime, id);
      await runtime.reeApi.patchReeIntent(reeId, { reeIntentPatch: intentPatch });
    },
    async deleteFile(id, path) {
      const reeId = await ensureReeId(runtime, id);
      await runtime.reeApi.deleteFileContent(reeId, path);
    },
    async getFileBytes(id, path) {
      const reeId = await ensureReeId(runtime, id);
      return runtime.reeApi.getFileBytes(reeId, path);
    },
    async sealRee(id, opts) {
      const reeId = await ensureReeId(runtime, id);
      return runtime.reeApi.sealRee(reeId, opts);
    },
    async getReeArchive(id) {
      const reeId = await ensureReeId(runtime, id);
      return runtime.reeApi.getReeArchive(reeId);
    },
    async resetWorkspaceRequest(id, request) {
      const reeId = await ensureReeId(runtime, id);
      const mode = request.mode || "clear";
      if (mode === "clear") {
        await runtime.reeApi.removeSource(reeId);
        return;
      }
      if (mode === "download") {
        await runtime.reeApi.acquireSource(
          reeId,
          toSourceAcquireRequest({
            originUrl: request.source,
            sourceType: request.sourceType,
            revision: request.revision,
          }),
        );
        return;
      }
      if (mode === "upload") {
        const archiveName = String(request.archiveName || "source.tar.gz");
        const init = await runtime.reeApi.initUpload(reeId, {
          fileName: archiveName,
          size: 0,
          contentType: "application/gzip",
        });
        if (request.archiveContentBase64) {
          const archiveData = decodeBase64ToArrayBuffer(String(request.archiveContentBase64));
          await runtime.reeApi.uploadSourceBytes(init.uploadUrl, archiveData);
        }
        await runtime.reeApi.completeUpload(reeId, init.uploadToken, archiveName);
        return;
      }
      throw new Error(`Unsupported workspace reset mode: ${mode}`);
    },
  };
}

export function useReeClient(): ReeClient<FileTreeNode, ReeProjectState> {
  const runtime = useApiRuntime();
  return useMemo(() => createReeClient(runtime), [runtime]);
}

function decodeBase64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}
