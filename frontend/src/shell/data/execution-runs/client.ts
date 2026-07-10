import type { ExecutionRun, ExecutionRunLogChunk } from "@core/execution/ExecutionRun";
import type { ExecutionRunStatus } from "@core/execution/ExecutionRunStatus";
import type { ReeId } from "@core/ree/ReeId";
import { useMemo } from "react";
import {
  toSourceAcquireRequest,
  type WorkflowRunDto,
  type WorkflowRunStatusDto,
} from "../../infra/api/apiTypes";
import { mapRunLogsToLines } from "../../infra/api/ExecutionRunsApi";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { ensureReeId } from "../client";

export interface ExecutionRunsClient {
  /**
   * Provision a brand-new workbench. Returns the freshly-minted reeId and the
   * background provisioning run, whose log feed streams the image pull live —
   * poll {@link getExecutionRunLogs} / {@link getExecutionRun} until terminal.
   *
   * ``image`` overrides the workbench base image; omitted/blank uses the server
   * default. ``agentId`` places the workbench on a specific agent (from GET
   * /agents); omitted/blank means "any connected agent".
   */
  createWorkspace(
    name?: string,
    image?: string,
    agentId?: string,
  ): Promise<{ reeId: string; run: ExecutionRun }>;
  startExecutionRun(
    id: ReeId | string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ): Promise<ExecutionRun>;
  getExecutionRun(id: ReeId | string, runId: string): Promise<ExecutionRun>;
  getExecutionRunLogs(
    id: ReeId | string,
    runId: string,
    cursor?: string,
  ): Promise<ExecutionRunLogChunk>;
  cancelExecutionRun(id: ReeId | string, runId: string): Promise<ExecutionRunStatus>;
}

function createExecutionRunsClient(runtime: ApiRuntimeValue): ExecutionRunsClient {
  return {
    async createWorkspace(name = "REE", image, agentId) {
      const run = await runtime.reeApi.createRee({
        sourceMode: "upload",
        name,
        workbenchImage: image?.trim() || undefined,
        agentId: agentId?.trim() || undefined,
      });
      return { reeId: run.reeId, run: mapRun(run) };
    },
    async startExecutionRun(id, scriptKey, params = {}) {
      const reeId = await ensureReeId(runtime, id);
      let run: WorkflowRunDto;
      switch (scriptKey) {
        case "build":
          run = await runtime.runsApi.createBuildRuntimeRun(reeId, {
            idempotencyKey:
              params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
          });
          break;
        case "hbom":
          run = await runtime.runsApi.createGenerateHbomRun(reeId, {
            idempotencyKey:
              params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
          });
          break;
        case "sbom":
          run = await runtime.runsApi.createGenerateSbomRun(reeId, {
            produced_runtime_path: String(params.produced_runtime_path ?? ""),
          });
          break;
        case "activation":
          run = await runtime.runsApi.createActivationTestRun(reeId, {});
          break;
        case "evaluate":
          run = await runtime.runsApi.createEvaluateRun(reeId, {
            strict: Boolean(params.strict),
          });
          break;
        case "source": {
          const mode = String(params.mode || "");
          if (mode === "download") {
            run = await runtime.reeApi.acquireSource(
              reeId,
              toSourceAcquireRequest({
                originUrl: params.source,
                sourceType: params.sourceType,
                revision: params.revision,
              }),
            );
            break;
          }
          if (mode === "upload") {
            const archiveName = String(params.archiveName || "source.tar.gz");
            const init = await runtime.reeApi.initUpload(reeId, {
              fileName: archiveName,
              size: 0,
              contentType: "application/gzip",
            });
            if (params.archiveContentBase64) {
              const archiveData = decodeBase64ToArrayBuffer(String(params.archiveContentBase64));
              await runtime.reeApi.uploadSourceBytes(init.uploadUrl, archiveData);
            }
            run = await runtime.reeApi.completeUpload(reeId, init.uploadToken, archiveName);
            break;
          }
          throw new Error("Unsupported source acquisition mode");
        }
        default:
          throw new Error(`Unsupported execution run operation: ${scriptKey}`);
      }
      return mapRun(run);
    },
    async getExecutionRun(id, runId) {
      const reeId = await ensureReeId(runtime, id);
      return mapRun(await runtime.runsApi.getRun(reeId, runId));
    },
    async getExecutionRunLogs(id, runId, cursor): Promise<ExecutionRunLogChunk> {
      const reeId = await ensureReeId(runtime, id);
      const logs = await runtime.runsApi.listRunLogs(reeId, runId, {
        cursor,
        limit: 200,
      });
      return {
        lines: mapRunLogsToLines(logs.entries),
        nextCursor: nextRunLogCursor(logs.nextCursor, logs.entries, cursor),
        hasMore: logs.hasMore,
      };
    },
    async cancelExecutionRun(id, runId) {
      const reeId = await ensureReeId(runtime, id);
      const response = await runtime.runsApi.cancelRun(reeId, runId);
      return mapStatus(response.status);
    },
  };
}

export function nextRunLogCursor(
  nextCursor: string | undefined,
  entries: Array<{ seq: number }>,
  currentCursor?: string,
): string | undefined {
  if (nextCursor) return nextCursor;
  const lastEntry = entries.at(-1);
  return lastEntry ? String(lastEntry.seq) : currentCursor;
}

export function useExecutionRunsClient(): ExecutionRunsClient {
  const runtime = useApiRuntime();
  return useMemo(() => createExecutionRunsClient(runtime), [runtime]);
}

function mapStatus(status: WorkflowRunStatusDto): ExecutionRunStatus {
  return status;
}

function mapRun(run: WorkflowRunDto): ExecutionRun {
  return {
    runId: run.runId,
    status: mapStatus(run.status),
    createdAt: run.createdAt,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
  };
}

function decodeBase64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}
