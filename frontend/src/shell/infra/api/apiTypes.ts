import type { components } from "./generated/openapi";

type Schema<TName extends keyof components["schemas"]> = components["schemas"][TName];

type NullToUndefined<TValue> = TValue extends null ? undefined : TValue;

type NullableToOptional<T> = {
  [K in keyof T]: NullToUndefined<T[K]>;
};

export type ApiErrorEnvelope = Schema<"ErrorEnvelope">;

export interface ApiListResponse<TItem> {
  items: TItem[];
  next_cursor?: string | null;
}

export type ReeSummary = Schema<"ReeSummary"> & {
  external_ref?: string | null;
};

export type ReeFileWire = {
  path: string;
  content?: string | null;
  size?: number | null;
  kind: "source" | "generated";
  etag?: string | null;
};

export type ReeArtifactFileWire = {
  path: string;
  content?: string | null;
  size?: number | null;
  kind: "ree";
  tag?: string | null;
};

export type ReeIntent = Schema<"ReeIntent">;

export type ReeSessionWire = {
  sealed_at?: string | null;
  seal_hash?: string | null;
  dependency_level?: number | null;
  environment_level?: number | null;
  machine_level?: number | null;
  detected_dependencies?: string | null;
  source_available?: boolean | null;
  source_acquired_by?: string | null;
  uploaded_archive?: string | null;
  source_snapshot_archive?: string | null;
  source_snapshot_captured_at?: string | null;
  source_included?: boolean | null;
  runtime_included?: boolean | null;
};

/** Display-ready source-repository facts as they cross the wire (snake_case). */
export type SourceRepoMetadataWire = {
  name: string;
  origin: string;
  acquired_by: string;
  source_type: string;
  swhid: string;
  size_bytes: number | null;
  size_label: string | null;
};

export type ConsistencyStaleInputWire = {
  input: string;
  recorded: string | null;
  current: string | null;
};

export type ConsistencyStepWire = {
  step: string;
  status: "fresh" | "stale" | "missing";
  run_id?: string | null;
  recorded_at?: string | null;
  stale_inputs?: ConsistencyStaleInputWire[];
  workspace_drift?: "clean" | "modified" | "unknown" | null;
};

/** Per-step freshness of recorded run receipts vs. the current tree. */
export type ConsistencyReportWire = {
  steps: ConsistencyStepWire[];
};

export type ReeDocument = Schema<"ReeDocument"> & {
  external_ref?: string | null;
  ree_intent: Partial<ReeIntent>;
  ree_session?: Partial<ReeSessionWire>;
  files?: ReeFileWire[];
  ree_files?: ReeArtifactFileWire[];
  draft_manifest?: Record<string, unknown>;
  source_repo?: SourceRepoMetadataWire;
  consistency?: ConsistencyReportWire;
  /** The image this REE's workbench was provisioned from. */
  workbench_image?: string | null;
};

export type ReeCreatePayload = Schema<"ReeCreatePayload">;

export type WorkbenchImageCatalog = Schema<"WorkbenchImageCatalog">;

/** One named starter-template variant for an REE-owned script; exactly one entry per list is the default. */
export type ScriptTemplateEntry = Schema<"ScriptTemplateEntry">;

/** Backend-owned starter templates for the REE-owned scripts (GET /script-templates). */
export type ScriptTemplateCatalog = Schema<"ScriptTemplateCatalog">;

/** A workbench agent connected to the control plane (GET /agents). */
export type AgentSummary = Schema<"AgentSummary">;

export type AgentList = Schema<"AgentList">;

export type ReeIntentPatchPayload = Schema<"ReeIntentPatchPayload">;

export type SourceAcquirePayload = Schema<"SourceAcquirePayload">;

/**
 * Shape an {@link SourceAcquirePayload} from loosely-typed download inputs,
 * applying the one normalization rule both acquire call sites (source execution
 * and workspace-reset fallback) must agree on: trim the revision and omit it
 * when blank, so the backend sees no revision rather than an empty string. Kept
 * here, next to the wire type, so the two paths cannot drift.
 */
export function toSourceAcquireRequest(input: {
  origin_url?: unknown;
  source_type?: unknown;
  revision?: unknown;
}): SourceAcquirePayload {
  const revision = typeof input.revision === "string" ? input.revision.trim() : "";
  return {
    origin_url: String(input.origin_url ?? ""),
    source_type: String(input.source_type ?? "git") as SourceAcquirePayload["source_type"],
    ...(revision ? { revision } : {}),
  };
}

export type UploadInitPayload = Schema<"UploadInitPayload">;

export type UploadInitResponse = Schema<"UploadInitResponse">;

export type CreateExperimentRunPayload = Schema<"CreateExperimentRunPayload">;

export type RunStatus = Schema<"RunSummary">["status"];

export type CreateBuildRuntimeRunPayload = Schema<"CreateBuildRuntimeRunPayload">;

export type CreateGenerateSbomRunPayload = Schema<"CreateGenerateSbomRunPayload">;

export type CreateGenerateHbomRunPayload = Schema<"CreateGenerateHbomRunPayload">;

export type CreateCrossCheckSbomRunPayload = Schema<"CreateCrossCheckSbomRunPayload">;

export type CreateActivationTestRunPayload = Schema<"CreateActivationTestRunPayload">;

export type CreateEvaluateRunPayload = Schema<"CreateEvaluateRunPayload">;

export type RunSummary = Schema<"RunSummary">;

export type RunList = Schema<"RunList">;

export type RunLogEntry = Schema<"RunLogEntry">;

export type RunLogPage = Schema<"RunLogPage">;

export type FileMutationResponse = NullableToOptional<Schema<"FileMutationResponse">>;

export type DeleteReeResponse = Schema<"DeleteReeResponse">;

export type ReprovisionResponse = Schema<"ReprovisionResponse">;
