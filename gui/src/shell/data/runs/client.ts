import type { ReeId } from "@core/ree/ReeId";
import type { ReeRun, ReeRunFailure, ReeRunLogChunk, ReeRunSummary } from "@core/runs/ReeRun";
import type { ReeRunStatus } from "@core/runs/ReeRunStatus";
import { useMemo } from "react";
import { type RunStatus, type RunSummary, toSourceAcquireRequest } from "../../infra/api/apiTypes";
import { mapRunLogsToLines } from "../../infra/api/ReeRunsApi";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import { ensureReeId } from "../client";

export interface ReeRunsClient {
  /**
   * Provision a brand-new workbench. Returns the freshly-minted reeId and the
   * background provisioning run, whose log feed streams the image pull live —
   * poll {@link getReeRunLogs} / {@link getReeRun} until terminal.
   *
   * ``image`` overrides the workbench base image; omitted/blank uses the server
   * default. ``agentId`` places the workbench on a specific agent (from GET
   * /agents); omitted/blank means "any connected agent".
   */
  createWorkspace(
    name?: string,
    image?: string,
    agentId?: string,
  ): Promise<{ reeId: string; run: ReeRun }>;
  /**
   * Make an REE be a downloaded REE bundle — the counterpart of the ree-archive
   * download. Uploads the bundle's bytes, then starts the background run that
   * restores them over whatever the REE holds, so it belongs on a freshly
   * provisioned workbench.
   */
  loadReeBundle(id: ReeId | string, bundle: File): Promise<ReeRun>;
  startReeRun(
    id: ReeId | string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ): Promise<ReeRun>;
  /**
   * Run one named experiment. Separate from {@link startReeRun} because the
   * experiment is addressed by name in the path rather than by a script key,
   * and returns the resolved reeId alongside the run so the caller can pin what
   * it observes — but it goes through this client like every other run, so the
   * cache seeding and cancellation in ``runs/mutations`` apply to it too.
   */
  startExperimentRun(
    id: ReeId | string,
    experimentName: string,
  ): Promise<{ reeId: string; run: ReeRun }>;
  /** Every recorded run for the REE, newest first. */
  listReeRuns(id: ReeId | string): Promise<ReeRunSummary[]>;
  getReeRun(id: ReeId | string, runId: string): Promise<ReeRun>;
  getReeRunLogs(id: ReeId | string, runId: string, cursor?: string): Promise<ReeRunLogChunk>;
  cancelReeRun(id: ReeId | string, runId: string): Promise<ReeRunStatus>;
}

function createReeRunsClient(runtime: ApiRuntimeValue): ReeRunsClient {
  return {
    async createWorkspace(name = "REE", image, agentId) {
      const run = await runtime.reeApi.createRee({
        name,
        workbench_image: image?.trim() || undefined,
        agent_id: agentId?.trim() || undefined,
      });
      return { reeId: run.ree_id, run: mapRun(run) };
    },
    async loadReeBundle(id, bundle) {
      const reeId = await ensureReeId(runtime, id);
      const archiveName = bundle.name || "ree.zip";
      const init = await runtime.reeApi.initBundleUpload(reeId, {
        file_name: archiveName,
        size: bundle.size,
        content_type: bundle.type || "application/zip",
      });
      await runtime.reeApi.uploadStagedBytes(init.upload_url, await bundle.arrayBuffer());
      return mapRun(await runtime.reeApi.loadReeBundle(reeId, init.upload_token, archiveName));
    },
    async startReeRun(id, scriptKey, params = {}) {
      const reeId = await ensureReeId(runtime, id);
      let run: RunSummary;
      switch (scriptKey) {
        case "build":
          run = await runtime.runsApi.createBuildRuntimeRun(reeId, {
            idempotency_key:
              params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
          });
          break;
        case "hbom":
          run = await runtime.runsApi.createGenerateHbomRun(reeId, {
            idempotency_key:
              params.idempotencyKey == null ? undefined : String(params.idempotencyKey),
          });
          break;
        case "sbom":
          run = await runtime.runsApi.createGenerateSbomRun(reeId, {});
          break;
        case "crosscheck":
          run = await runtime.runsApi.createCrossCheckSbomRun(reeId, {});
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
                origin_url: params.source,
                source_type: params.sourceType,
                revision: params.revision,
              }),
            );
            break;
          }
          if (mode === "upload") {
            const archiveName = String(params.archiveName || "source.tar.gz");
            const init = await runtime.reeApi.initUpload(reeId, {
              file_name: archiveName,
              size: 0,
              content_type: "application/gzip",
            });
            if (params.archiveContentBase64) {
              const archiveData = decodeBase64ToArrayBuffer(String(params.archiveContentBase64));
              await runtime.reeApi.uploadStagedBytes(init.upload_url, archiveData);
            }
            run = await runtime.reeApi.completeUpload(reeId, init.upload_token, archiveName);
            break;
          }
          throw new Error("Unsupported source acquisition mode");
        }
        default:
          throw new Error(`Unsupported execution run operation: ${scriptKey}`);
      }
      return mapRun(run);
    },
    async startExperimentRun(id, experimentName) {
      const reeId = await ensureReeId(runtime, id);
      const run = await runtime.runsApi.createExperimentRun(reeId, experimentName, {});
      return { reeId, run: mapRun(run) };
    },
    async listReeRuns(id) {
      const reeId = await ensureReeId(runtime, id);
      const { runs } = await runtime.runsApi.listRuns(reeId);
      return runs.map((run) => ({ ...mapRun(run), operation: run.operation }));
    },
    async getReeRun(id, runId) {
      const reeId = await ensureReeId(runtime, id);
      return mapRun(await runtime.runsApi.getRun(reeId, runId));
    },
    async getReeRunLogs(id, runId, cursor): Promise<ReeRunLogChunk> {
      const reeId = await ensureReeId(runtime, id);
      const logs = await runtime.runsApi.listRunLogs(reeId, runId, {
        cursor,
        limit: 200,
      });
      return {
        lines: mapRunLogsToLines(logs.entries),
        nextCursor: nextRunLogCursor(logs.next_cursor ?? undefined, logs.entries, cursor),
        hasMore: logs.has_more,
      };
    },
    async cancelReeRun(id, runId) {
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

export function useReeRunsClient(): ReeRunsClient {
  const runtime = useApiRuntime();
  return useMemo(() => createReeRunsClient(runtime), [runtime]);
}

function mapStatus(status: RunStatus): ReeRunStatus {
  return status;
}

function mapRun(run: RunSummary): ReeRun {
  return {
    runId: run.run_id,
    status: mapStatus(run.status),
    createdAt: run.created_at,
    startedAt: run.started_at ?? undefined,
    finishedAt: run.finished_at ?? undefined,
    failure: mapFailure(run.failure),
    outputs: run.outputs,
  };
}

/** Reconcile the wire failure (nullable) with the domain's optional shape. */
function mapFailure(failure: RunSummary["failure"]): ReeRunFailure | undefined {
  if (!failure) {
    return undefined;
  }
  return {
    category: failure.category,
    message: failure.message,
    retryable: failure.retryable,
    origin: failure.origin,
    details: failure.details ?? undefined,
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
