import type { ReeId } from "@core/ree/ReeId";
import type { ReeIntentPatch } from "@core/ree/reePatch";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { WorkspaceResetPayload } from "@core/workspace/WorkspaceReset";
import type { ReeProject, WorkspaceBinaryDownload } from "@core/workspace/WorkspaceTypes";
import { useMemo } from "react";
import { ApiRequestError } from "../../infra/api/ApiClient";
import {
  type ReeDocument,
  type ReeIntentPatchPayload,
  toSourceAcquireRequest,
} from "../../infra/api/apiTypes";
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
  getReeFileBytes(id: ReeId | string, path: string): Promise<ArrayBuffer>;
  sealRee(
    id: ReeId | string,
    opts: { includeSource: boolean; includeRuntime: boolean; includeResults: boolean },
  ): Promise<ReeDocument>;
  getReeArchive(id: ReeId | string): Promise<WorkspaceBinaryDownload>;
  resetWorkspaceRequest(id: ReeId | string, request: WorkspaceResetPayload): Promise<void>;
  /** End the REE session and remove its workbench. Succeeds if it is already gone. */
  releaseRee(id: ReeId | string): Promise<void>;
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
      // The domain serializers emit loosely-typed records in the wire's shape;
      // the backend validates the patch strictly (unknown keys are rejected).
      await runtime.reeApi.patchReeIntent(reeId, {
        ree_intent_patch: intentPatch as ReeIntentPatchPayload["ree_intent_patch"],
      });
    },
    async deleteFile(id, path) {
      const reeId = await ensureReeId(runtime, id);
      await runtime.reeApi.deleteFileContent(reeId, path);
    },
    async getReeFileBytes(id, path) {
      const reeId = await ensureReeId(runtime, id);
      return runtime.reeApi.getReeFileBytes(reeId, path);
    },
    async sealRee(id, opts) {
      const reeId = await ensureReeId(runtime, id);
      return runtime.reeApi.sealRee(reeId, opts);
    },
    async getReeArchive(id) {
      const reeId = await ensureReeId(runtime, id);
      return runtime.reeApi.getReeArchive(reeId);
    },
    async releaseRee(id) {
      const reeId = await ensureReeId(runtime, id);
      try {
        await runtime.reeApi.deleteRee(reeId);
      } catch (err) {
        // A 404 means the backend already has no session for this REE, which is
        // the outcome release was asking for. Reporting it as a failure would
        // strand the caller on a workbench that no longer exists.
        if (!(err instanceof ApiRequestError) || err.status !== 404) throw err;
      }
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
            origin_url: request.source,
            source_type: request.sourceType,
            revision: request.revision,
          }),
        );
        return;
      }
      if (mode === "upload") {
        const archiveName = String(request.archiveName || "source.tar.gz");
        const init = await runtime.reeApi.initUpload(reeId, {
          file_name: archiveName,
          size: 0,
          content_type: "application/gzip",
        });
        if (request.archiveContentBase64) {
          const archiveData = decodeBase64ToArrayBuffer(String(request.archiveContentBase64));
          await runtime.reeApi.uploadStagedBytes(init.upload_url, archiveData);
        }
        await runtime.reeApi.completeUpload(reeId, init.upload_token, archiveName);
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
