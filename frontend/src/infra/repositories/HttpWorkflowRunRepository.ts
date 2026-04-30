import type {
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../application/ports/repositoryTypes";
import type { WorkflowRunRepository } from "../../application/ports/WorkflowRunRepository";
import type { WorkflowRunDto, WorkflowRunStatusDto } from "../api";
import { mapRunLogsToLegacy } from "../api";
import type { HttpRepositoryClient } from "./HttpRepositoryClient";

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

export function createHttpWorkflowRunRepository(
  repositoryClient: HttpRepositoryClient,
): WorkflowRunRepository {
  return {
    async startWorkflowRun(id, scriptKey, params = {}) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      let run: WorkflowRunDto;
      switch (scriptKey) {
        case "build":
          run = await repositoryClient.runsApi.createBuildRuntimeRun(workspaceId, {
            build_runtime_script_path: String(
              params.build_runtime_script_path ??
                params.build_runtime_script ??
                params.script ??
                "",
            ),
            produced_runtime_path: String(
              params.produced_runtime_path ?? params.runtime ?? params._expectedOutput ?? "",
            ),
          });
          break;
        case "hbom":
          run = await repositoryClient.runsApi.createGenerateHbomRun(workspaceId, {
            idempotencyKey:
              params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
          });
          break;
        case "sbom":
          run = await repositoryClient.runsApi.createGenerateSbomRun(workspaceId, {
            produced_runtime_path: String(
              params.produced_runtime_path ?? params.runtime ?? params._expectedOutput ?? "",
            ),
          });
          break;
        case "activation":
          run = await repositoryClient.runsApi.createActivationTestRun(workspaceId, {
            activation_script_path: String(
              params.activation_script_path ?? params.activation_script ?? "",
            ),
          });
          break;
        case "evaluate":
          run = await repositoryClient.runsApi.createEvaluateRun(workspaceId, {
            strict: Boolean(params.strict),
            swhid_check: Boolean(params.swhid_check),
          });
          break;
        case "source": {
          const mode = String(params.mode || "");
          if (mode === "download") {
            run = await repositoryClient.workspaceApi.acquireSource(workspaceId, {
              originUrl: String(params.source ?? ""),
              sourceType: String(params.sourceType ?? "git") as "git" | "tarball" | "zip",
            });
            break;
          }
          if (mode === "upload") {
            const archiveName = String(params.archiveName || "source.tar.gz");
            const init = await repositoryClient.workspaceApi.initUpload(workspaceId, {
              fileName: archiveName,
              size: 0,
              contentType: "application/gzip",
            });
            if (params.archiveContentBase64) {
              const archiveData = decodeBase64ToArrayBuffer(String(params.archiveContentBase64));
              await repositoryClient.workspaceApi.uploadSourceBytes(init.uploadUrl, archiveData);
            }
            run = await repositoryClient.workspaceApi.completeUpload(
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
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      return mapRun(await repositoryClient.runsApi.getRun(workspaceId, runId));
    },
    async getWorkflowRunLogs(id, runId, cursor): Promise<WorkflowRunLogChunk> {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      const logs = await repositoryClient.runsApi.listRunLogs(workspaceId, runId, {
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
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      const response = await repositoryClient.runsApi.cancelRun(workspaceId, runId);
      return mapStatus(response.status);
    },
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
