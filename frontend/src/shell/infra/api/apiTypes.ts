import type { ConsistencyReport } from "@core/ree-steps/sealConsistency";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface ApiListResponse<TItem> {
  items: TItem[];
  nextCursor?: string;
}

export interface ReeSummaryDto {
  reeId: string;
  externalRef?: string;
  name: string;
  status: "draft" | "ready" | "sealed" | "archived";
  createdAt: string;
  updatedAt: string;
}

export interface ReeFileDto {
  path: string;
  content?: string;
  size?: number;
  kind: "source" | "generated";
  etag?: string;
}

export interface ReeArtifactFileDto {
  path: string;
  content?: string;
  size?: number;
  kind: "ree";
  tag?: string;
}

export interface ReeIntentDto {
  name: string;
  catalog_metadata: {
    description?: string;
    version?: string;
    website?: string;
    keywords?: string[];
    contributors?: Array<{
      identifier?: string;
      name?: string;
      affiliation_name?: string;
      affiliation_identifier?: string;
    }>;
    corresponding_author_identifier?: string | null;
  };
  origin_url: string;
  source_type: string;
  runtime: string;
  lifecycle?: Record<string, unknown>;
  sbom: string;
  activation?: Record<string, unknown>;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  hardware_description: Record<string, unknown>;
  experiments?: Array<Record<string, unknown>>;
}

export interface ReeSessionDto {
  sealed_at?: string;
  seal_hash?: string;
  dependency_level?: number;
  environment_level?: number;
  machine_level?: number;
  detected_dependencies?: string;
  source_available?: boolean;
  source_acquired_by?: string;
  uploaded_archive?: string;
  source_snapshot_archive?: string;
  source_snapshot_captured_at?: string;
  source_included?: boolean;
  runtime_included?: boolean;
}

export interface ReeDetailDto extends ReeSummaryDto {
  reeIntent: Partial<ReeIntentDto>;
  reeSession?: Partial<ReeSessionDto>;
  files?: ReeFileDto[];
  reeFiles?: ReeArtifactFileDto[];
  draftManifest?: Record<string, unknown>;
  // The backend emits this already camelCased and the frontend renders it
  // untouched, so the wire shape and the domain type are one and the same.
  sourceRepo?: SourceRepoMetadata;
  // Per-step freshness of recorded run receipts vs. the current tree; emitted
  // camelCased by the backend and rendered untouched, like sourceRepo.
  consistency?: ConsistencyReport;
  /** The image this REE's workbench was provisioned from. */
  workbenchImage?: string;
}

export interface CreateReeRequestDto {
  name?: string;
  /** Image to provision the workbench from; omitted falls back to the server default. */
  workbenchImage?: string;
  /** Agent to place the workbench on (GET /agents); omitted means "any connected agent". */
  agentId?: string;
}

/** A base image offered for workbench provisioning (GET /workbench/images). */
export interface WorkbenchImageDto {
  id: string;
  ref: string;
  label: string;
  description: string;
}

export interface WorkbenchImageCatalogDto {
  images: WorkbenchImageDto[];
  /** Id of the image used when a provisioning request omits one. */
  defaultId: string;
}

/** One named starter-template variant for an REE-owned script; the first entry of a list is the default. */
export interface ScriptTemplateEntryDto {
  key: string;
  label: string;
  description: string;
  body: string;
}

/** Backend-owned starter templates for the REE-owned scripts (GET /script-templates). */
export interface ScriptTemplateCatalogDto {
  build: {
    path: string;
    /** Named variants (currently only `docker`); the first is the default a fresh REE is seeded with. */
    templates: ScriptTemplateEntryDto[];
  };
  activation: {
    runScriptPath: string;
    /** Where an activation verify script belongs; declaring one is an explicit act. */
    verifyScriptPath: string;
    templates: ScriptTemplateEntryDto[];
  };
  experiment: {
    /** Path conventions with a `{slug}` placeholder (experiment name, whitespace → hyphens). */
    runScriptPathPattern: string;
    verifyScriptPathPattern: string;
    templates: ScriptTemplateEntryDto[];
  };
  /** Verify templates shared across runnables; the first entry is the default. */
  verify: ScriptTemplateEntryDto[];
}

/** A workbench agent connected to the control plane (GET /agents). */
export interface AgentSummaryDto {
  agentId: string;
  hostname: string;
  version: string;
  dockerMode: string;
  /** ISO 8601 UTC timestamp of when the agent dialed in. */
  connectedAt: string;
  status: string;
}

export interface AgentListDto {
  agents: AgentSummaryDto[];
}

export interface PatchReeRequestDto {
  reeIntentPatch: Record<string, unknown>;
  expectedVersion?: string;
}

export interface SourceAcquireRequestDto {
  originUrl: string;
  sourceType: "git" | "tarball" | "zip";
  /** Git revision (commit, branch, or tag) to pin the fetch to; blank means default-branch HEAD. */
  revision?: string;
}

/**
 * Shape an {@link SourceAcquireRequestDto} from loosely-typed download inputs,
 * applying the one normalization rule both acquire call sites (source execution
 * and workspace-reset fallback) must agree on: trim the revision and omit it
 * when blank, so the backend sees no revision rather than an empty string. Kept
 * here, next to the DTO, so the two paths cannot drift.
 */
export function toSourceAcquireRequest(input: {
  originUrl?: unknown;
  sourceType?: unknown;
  revision?: unknown;
}): SourceAcquireRequestDto {
  const revision = typeof input.revision === "string" ? input.revision.trim() : "";
  return {
    originUrl: String(input.originUrl ?? ""),
    sourceType: String(input.sourceType ?? "git") as "git" | "tarball" | "zip",
    ...(revision ? { revision } : {}),
  };
}

export interface UploadInitRequestDto {
  fileName: string;
  size: number;
  contentType: string;
}

export interface UploadInitResponseDto {
  uploadUrl: string;
  uploadToken: string;
  expiresAt: string;
}

export type ReeRunOperationDto =
  | "provision"
  | "evaluate"
  | "build"
  | "hbom"
  | "sbom"
  | "activation"
  | "source"
  | "swh"
  | "zenodo"
  | "dataverse"
  | "experiment";

// No fields yet — kept as the extension point for future run options.
export type CreateExperimentRunRequestDto = Record<string, never>;

export type ReeRunStatusDto =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export interface CreateBuildRuntimeRunRequestDto {
  idempotencyKey?: string;
}

export interface CreateGenerateSbomRunRequestDto {
  produced_runtime_path: string;
  idempotencyKey?: string;
}

export interface CreateGenerateHbomRunRequestDto {
  idempotencyKey?: string;
}

export interface CreateCrossCheckSbomRunRequestDto {
  idempotencyKey?: string;
}

export interface CreateActivationTestRunRequestDto {
  idempotencyKey?: string;
}

export interface CreateEvaluateRunRequestDto {
  strict: boolean;
  idempotencyKey?: string;
}

export interface ReeRunDto {
  runId: string;
  reeId: string;
  operation: ReeRunOperationDto;
  status: ReeRunStatusDto;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  outputs?: Record<string, unknown>;
}

export interface ReeRunListDto {
  runs: ReeRunDto[];
}

export interface ReeRunLogEntryDto {
  seq: number;
  ts: string;
  stream: "stdout" | "stderr" | "system";
  level: "info" | "warn" | "error" | "debug";
  message: string;
}

export interface ReeRunLogsDto {
  entries: ReeRunLogEntryDto[];
  nextCursor?: string;
  hasMore: boolean;
  runStatus: ReeRunStatusDto;
}
