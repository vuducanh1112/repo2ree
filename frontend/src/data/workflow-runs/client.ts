import { useMemo } from "react";
import type {
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../domain/workflow/WorkflowRun";
import type { WorkflowRunDto, WorkflowRunStatusDto } from "../../infra/api/apiTypes";
import { mapRunLogsToLegacy } from "../../infra/api/WorkflowRunsApi";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { ensureWorkspaceId } from "../client";

export interface WorkflowRunsClient {
  startWorkflowRun(
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ): Promise<WorkflowRunRecord>;
  getWorkflowRun(id: string, runId: string): Promise<WorkflowRunRecord>;
  getWorkflowRunLogs(id: string, runId: string, cursor?: string): Promise<WorkflowRunLogChunk>;
  cancelWorkflowRun(id: string, runId: string): Promise<WorkflowRunStatus>;
}

function createWorkflowRunsClient(runtime: ApiRuntimeValue): WorkflowRunsClient {
  return {
    async startWorkflowRun(id, scriptKey, params = {}) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      let run: WorkflowRunDto;
      switch (scriptKey) {
        case "build":
          run = await runtime.runsApi.createBuildRuntimeRun(workspaceId, {
            build_runtime_script_path: String(params.build_runtime_script_path ?? ""),
            produced_runtime_path: String(params.produced_runtime_path ?? ""),
          });
          break;
        case "hbom":
          run = await runtime.runsApi.createGenerateHbomRun(workspaceId, {
            idempotencyKey:
              params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
          });
          break;
        case "sbom":
          run = await runtime.runsApi.createGenerateSbomRun(workspaceId, {
            produced_runtime_path: String(params.produced_runtime_path ?? ""),
          });
          break;
        case "activation":
          run = await runtime.runsApi.createActivationTestRun(workspaceId, {
            activation_script_path: String(params.activation_script_path ?? ""),
          });
          break;
        case "evaluate":
          run = await runtime.runsApi.createEvaluateRun(workspaceId, {
            strict: Boolean(params.strict),
            swhid_check: Boolean(params.swhid_check),
          });
          break;
        case "source": {
          const mode = String(params.mode || "");
          if (mode === "download") {
            run = await runtime.workspaceApi.acquireSource(workspaceId, {
              originUrl: String(params.source ?? ""),
              sourceType: String(params.sourceType ?? "git") as "git" | "tarball" | "zip",
            });
            break;
          }
          if (mode === "upload") {
            const archiveName = String(params.archiveName || "source.tar.gz");
            const init = await runtime.workspaceApi.initUpload(workspaceId, {
              fileName: archiveName,
              size: 0,
              contentType: "application/gzip",
            });
            if (params.archiveContentBase64) {
              const archiveData = decodeBase64ToArrayBuffer(String(params.archiveContentBase64));
              await runtime.workspaceApi.uploadSourceBytes(init.uploadUrl, archiveData);
            }
            run = await runtime.workspaceApi.completeUpload(
              workspaceId,
              init.uploadToken,
              archiveName,
            );
            break;
          }
          throw new Error("Unsupported source workflow mode");
        }
        default:
          throw new Error(`Unsupported remote workflow operation: ${scriptKey}`);
      }
      return mapRun(run);
    },
    async getWorkflowRun(id, runId) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      return mapRun(await runtime.runsApi.getRun(workspaceId, runId));
    },
    async getWorkflowRunLogs(id, runId, cursor): Promise<WorkflowRunLogChunk> {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      const logs = await runtime.runsApi.listRunLogs(workspaceId, runId, {
        cursor,
        limit: 200,
      });
      return {
        lines: mapRunLogsToLegacy(logs.entries),
        nextCursor: logs.nextCursor,
        hasMore: logs.hasMore,
      };
    },
    async cancelWorkflowRun(id, runId) {
      const workspaceId = await ensureWorkspaceId(runtime, id);
      const response = await runtime.runsApi.cancelRun(workspaceId, runId);
      return mapStatus(response.status);
    },
  };
}

export function useWorkflowRunsClient(): WorkflowRunsClient {
  const runtime = useApiRuntime();
  return useMemo(() => createWorkflowRunsClient(runtime), [runtime]);
}

function mapStatus(status: WorkflowRunStatusDto): WorkflowRunStatus {
  return status;
}

function mapRun(run: WorkflowRunDto): WorkflowRunRecord {
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
