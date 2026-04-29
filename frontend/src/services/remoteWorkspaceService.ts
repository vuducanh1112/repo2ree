import type { WorkflowRunDto, WorkflowRunStatusDto, WorkspaceDetailDto } from "../api";
import { ApiClient, mapRunLogsToLegacy, WorkflowRunsApi, WorkspaceApi } from "../api";
import { mapWorkspaceDraftToRee } from "../infra/api/reeMappers";
import type { FileTreeNode, Ree } from "../types";
import type { ReeFile } from "../types/ree";
import type {
  IWorkspaceService,
  LogLine,
  ReeProject,
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkspaceResetPayload,
} from "./workspaceService";
import { parseWorkspaceResetPayload } from "./workspaceService";

interface CreateRemoteWorkspaceServiceOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
  initialWorkspaceId?: string;
}

const TERMINAL_STATUSES = new Set<WorkflowRunStatusDto>(["succeeded", "failed", "canceled"]);

function mapStatus(status: WorkflowRunStatusDto): WorkflowRunRecord["status"] {
  return status;
}

function upsertTreeFile(
  roots: FileTreeNode[],
  relativePath: string,
  content: string | undefined,
  size: number | undefined,
  kind: string,
): void {
  const parts = relativePath.split("/").filter(Boolean);
  if (parts.length === 0) {
    return;
  }

  let cursor = roots;
  let prefix = "";
  for (let i = 0; i < parts.length - 1; i += 1) {
    const segment = parts[i];
    prefix = prefix ? `${prefix}/${segment}` : segment;
    let folder = cursor.find((node) => node.type === "folder" && node.name === segment);
    if (!folder) {
      folder = {
        id: `remote-dir-${prefix}`,
        name: segment,
        type: "folder",
        children: [],
      };
      cursor.push(folder);
    }
    if (!folder.children) {
      folder.children = [];
    }
    cursor = folder.children;
  }

  const fileName = parts[parts.length - 1];
  const fileId = `remote-${relativePath}`;
  const fileNode: FileTreeNode = {
    id: fileId,
    name: fileName,
    type: "file",
    content,
    size,
    tag: kind,
  };
  const existingIndex = cursor.findIndex((node) => node.type === "file" && node.name === fileName);
  if (existingIndex >= 0) {
    cursor[existingIndex] = fileNode;
  } else {
    cursor.push(fileNode);
  }
}

function mapWorkspace(workspace: WorkspaceDetailDto): ReeProject<FileTreeNode> {
  const files: FileTreeNode[] = [];
  for (const file of workspace.files || []) {
    if (!file.path) {
      continue;
    }
    upsertTreeFile(files, file.path, file.content, file.size, file.kind);
  }

  const reeFiles: ReeFile[] = (workspace.reeFiles || []).map((file, index) => ({
    id: `remote-ree-${index}-${file.path}`,
    name: file.path,
    type: "file",
    tag: file.tag || "REE",
    content: file.content,
    size: file.size,
  }));
  const ree: Ree = mapWorkspaceDraftToRee(workspace);

  return {
    id: workspace.reeId,
    files,
    reeFiles,
    ree,
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function decodeBase64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

export function createRemoteWorkspaceService(
  options: CreateRemoteWorkspaceServiceOptions = {},
): IWorkspaceService<FileTreeNode> {
  const client = new ApiClient({
    baseUrl: options.baseUrl,
    headers: options.headers,
  });
  const workspaceApi = new WorkspaceApi(client);
  const runsApi = new WorkflowRunsApi(client);
  let resolvedWorkspaceId: string | null = options.initialWorkspaceId || null;

  const ensureWorkspaceId = async (requestedId: string): Promise<string> => {
    if (requestedId && requestedId !== "active") {
      return requestedId;
    }
    if (resolvedWorkspaceId) {
      return resolvedWorkspaceId;
    }

    const created = await workspaceApi.createWorkspace({
      sourceMode: "upload",
      name: "Explorer Workspace",
    });
    resolvedWorkspaceId = created.reeId;
    return resolvedWorkspaceId;
  };

  const startWorkflowRun = async (
    id: string,
    scriptKey: string,
    params: Record<string, string | boolean | number | null | undefined> = {},
  ): Promise<WorkflowRunRecord> => {
    const workspaceId = await ensureWorkspaceId(id);
    let run: WorkflowRunDto;
    if (scriptKey === "build") {
      run = await runsApi.createBuildRuntimeRun(workspaceId, {
        build_runtime_script_path: String(
          params.build_runtime_script_path ?? params.build_runtime_script ?? params.script ?? "",
        ),
        produced_runtime_path: String(
          params.produced_runtime_path ?? params.runtime ?? params._expectedOutput ?? "",
        ),
      });
    } else if (scriptKey === "hbom") {
      run = await runsApi.createGenerateHbomRun(workspaceId, {
        idempotencyKey: params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
      });
    } else if (scriptKey === "sbom") {
      run = await runsApi.createGenerateSbomRun(workspaceId, {
        produced_runtime_path: String(
          params.produced_runtime_path ?? params.runtime ?? params._expectedOutput ?? "",
        ),
      });
    } else if (scriptKey === "activation") {
      run = await runsApi.createActivationTestRun(workspaceId, {
        activation_script_path: String(
          params.activation_script_path ?? params.activation_script ?? "",
        ),
      });
    } else if (scriptKey === "evaluate") {
      run = await runsApi.createEvaluateRun(workspaceId, {
        strict: Boolean(params.strict),
        swhid_check: Boolean(params.swhid_check),
      });
    } else if (scriptKey === "source") {
      const mode = String(params.mode || "");
      if (mode === "download") {
        run = await workspaceApi.acquireSource(workspaceId, {
          originUrl: String(params.source ?? ""),
          sourceType: String(params.sourceType ?? "git") as "git" | "tarball" | "zip",
        });
      } else if (mode === "upload") {
        const archiveName = String(params.archiveName || "source.tar.gz");
        const init = await workspaceApi.initUpload(workspaceId, {
          fileName: archiveName,
          size: 0,
          contentType: "application/gzip",
        });
        if (params.archiveContentBase64) {
          const archiveData = decodeBase64ToArrayBuffer(String(params.archiveContentBase64));
          await workspaceApi.uploadSourceBytes(init.uploadUrl, archiveData);
        }
        run = await workspaceApi.completeUpload(workspaceId, init.uploadToken, archiveName);
      } else {
        throw new Error("Unsupported source workflow mode");
      }
    } else {
      throw new Error(`Unsupported remote workflow operation: ${scriptKey}`);
    }
    return {
      runId: run.runId,
      status: mapStatus(run.status),
      createdAt: run.createdAt,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
    };
  };

  const getWorkflowRun = async (id: string, runId: string): Promise<WorkflowRunRecord> => {
    const workspaceId = await ensureWorkspaceId(id);
    const run = await runsApi.getRun(workspaceId, runId);
    return {
      runId: run.runId,
      status: mapStatus(run.status),
      createdAt: run.createdAt,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
    };
  };

  const getWorkflowRunLogs = async (
    id: string,
    runId: string,
    cursor?: string,
  ): Promise<WorkflowRunLogChunk> => {
    const workspaceId = await ensureWorkspaceId(id);
    const logs = await runsApi.listRunLogs(workspaceId, runId, { cursor, limit: 200 });
    const lines = mapRunLogsToLegacy(logs.entries);
    return {
      lines,
      nextCursor: logs.nextCursor,
      hasMore: logs.hasMore,
    };
  };

  const cancelWorkflowRun = async (id: string, runId: string) => {
    const workspaceId = await ensureWorkspaceId(id);
    const response = await runsApi.cancelRun(workspaceId, runId);
    return mapStatus(response.status);
  };

  const resetWorkspaceRequest = async (
    id: string,
    request: WorkspaceResetPayload,
  ): Promise<void> => {
    const workspaceId = await ensureWorkspaceId(id);
    const mode = request.mode || "clear";
    if (mode === "clear") {
      await workspaceApi.removeSource(workspaceId);
      return;
    }

    if (mode === "upload") {
      const archiveName = request.archiveName || "source.tar.gz";
      const init = await workspaceApi.initUpload(workspaceId, {
        fileName: archiveName,
        size: 0,
        contentType: "application/gzip",
      });
      if (request.archiveContentBase64) {
        const archiveData = decodeBase64ToArrayBuffer(request.archiveContentBase64);
        await workspaceApi.uploadSourceBytes(init.uploadUrl, archiveData);
      }
      await workspaceApi.completeUpload(workspaceId, init.uploadToken, archiveName);
      return;
    }

    if (!request.source || !request.sourceType) {
      throw new Error("Source URL and source type are required for download mode");
    }

    await workspaceApi.acquireSource(workspaceId, {
      originUrl: request.source,
      sourceType: request.sourceType as "git" | "tarball" | "zip",
    });
  };

  const collectRunLogs = async (id: string, runId: string): Promise<LogLine[]> => {
    const lines: LogLine[] = [];
    let cursor: string | undefined;
    for (let i = 0; i < 15; i += 1) {
      const chunk = await getWorkflowRunLogs(id, runId, cursor);
      lines.push(...chunk.lines);
      if (!chunk.hasMore || !chunk.nextCursor) {
        break;
      }
      cursor = chunk.nextCursor;
    }
    return lines;
  };

  return {
    getWorkspace: async (id: string): Promise<ReeProject<FileTreeNode>> => {
      const workspaceId = await ensureWorkspaceId(id);
      const workspace = await workspaceApi.getWorkspace(workspaceId);
      return mapWorkspace(workspace);
    },
    updateFile: async (id: string, path: string, content: string): Promise<void> => {
      const workspaceId = await ensureWorkspaceId(id);
      await workspaceApi.putFileContent(workspaceId, { path, content });
    },
    updateReeDraft: async (id: string, reePatch: Record<string, unknown>): Promise<void> => {
      const workspaceId = await ensureWorkspaceId(id);
      await workspaceApi.patchWorkspace(workspaceId, { reePatch });
    },
    getFileBytes: async (id: string, path: string): Promise<ArrayBuffer> => {
      const workspaceId = await ensureWorkspaceId(id);
      return workspaceApi.getFileBytes(workspaceId, path);
    },
    getReeArchive: async (id: string) => {
      const workspaceId = await ensureWorkspaceId(id);
      return workspaceApi.getReeArchive(workspaceId);
    },
    deleteFile: async (id: string, path: string): Promise<void> => {
      const workspaceId = await ensureWorkspaceId(id);
      await workspaceApi.deleteFileContent(workspaceId, path);
    },
    runScript: async (id: string, scriptKey: string): Promise<{ lines: LogLine[]; ts: string }> => {
      const run = await startWorkflowRun(id, scriptKey);
      let latestRun = run;
      for (let i = 0; i < 90; i += 1) {
        if (TERMINAL_STATUSES.has(latestRun.status)) {
          const lines = await collectRunLogs(id, run.runId);
          return { lines, ts: latestRun.finishedAt || new Date().toISOString() };
        }
        await sleep(i < 10 ? 1000 : i < 30 ? 2500 : 5000);
        latestRun = await getWorkflowRun(id, run.runId);
      }
      const lines = await collectRunLogs(id, run.runId);
      lines.push({ type: "warn", msg: "Run still in progress while polling window ended" });
      return { lines, ts: new Date().toISOString() };
    },
    resetWorkspaceRequest,
    resetWorkspace: async (id: string, newSource: string): Promise<void> => {
      const payload = parseWorkspaceResetPayload(newSource, "git");
      await resetWorkspaceRequest(id, payload);
    },
    startWorkflowRun,
    getWorkflowRun,
    getWorkflowRunLogs,
    cancelWorkflowRun,
  };
}
