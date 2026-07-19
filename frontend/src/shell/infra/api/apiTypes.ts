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

export type ReeSummary = Schema<"ReeSummary">;

/** Display-ready source-repository facts as they cross the wire (snake_case). */
export type SourceRepoMetadataWire = Schema<"SourceRepoMetadata">;

/** Per-step freshness of recorded run receipts vs. the current tree. */
export type ConsistencyReportWire = Schema<"ConsistencyReport">;

export type ReeDocument = Schema<"ReeDocument">;

export type ReproducibilityScoreCardWire = Schema<"ReproducibilityScoreCard">;

export type ReproducibilityReportWire = Schema<"ReproducibilityReport">;

export type ReeCreatePayload = Schema<"ReeCreatePayload">;

export type WorkbenchImageCatalog = Schema<"WorkbenchImageCatalog">;

/** One named starter-template variant for an REE-owned script; exactly one entry per list is the default. */
export type ScriptTemplateEntry = Schema<"ScriptTemplateEntry">;

/** Backend-owned starter templates for the REE-owned scripts (GET /script-templates). */
export type ScriptTemplateCatalog = Schema<"ScriptTemplateCatalog">;

/** A workbench agent connected to the control plane (GET /agents). */
export type AgentSummary = Schema<"AgentSummary">;

export type AgentList = Schema<"AgentList">;

/**
 * The PATCH wire applies only the keys actually sent (``exclude_unset`` on the
 * backend), so any subset of intent fields is a valid patch. The generated
 * Input type marks defaulted fields as required; relax that here.
 */
export type ReeIntentPatchPayload = Omit<Schema<"ReeIntentPatchPayload">, "ree_intent_patch"> & {
  ree_intent_patch?: Partial<Schema<"ReeIntent-Input">>;
};

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
