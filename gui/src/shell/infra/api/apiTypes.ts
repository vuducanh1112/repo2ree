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

export type OperationHistoryWire = Schema<"OperationHistory">;

export type ReeSummary = Schema<"ReeSummary">;

export type ReviewRecordWire = Schema<"ReviewRecord">;

export type ReviewStepStateWire = Schema<"ReviewStepState">;

export type ExperimentEnvironmentComparisonWire = Schema<"ExperimentEnvironmentComparison">;

export type PackageDeltaWire = Schema<"PackageDeltaRecord">;

export type ActivationOutcomeWire = Schema<"ActivationOutcome">;

export type ExperimentComparisonWire = Schema<"ExperimentComparison">;

export type ReviewSetWire = Schema<"ReviewSet">;

export type ReviewAcquireSourcePayload = Schema<"ReviewAcquireSourcePayload">;

export type ReviewBuildExperimentEnvironmentPayload =
  Schema<"ReviewBuildExperimentEnvironmentPayload">;

export type ReeDocument = Schema<"ReeDocument">;
export type ReeState = Schema<"ReeState">;
export type BuildInfo = Schema<"BuildInfo">;

export type ReproducibilityReportWire = Schema<"ReproducibilityReport">;

export type ReeCreatePayload = Schema<"ReeCreatePayload">;

export type StoreSummary = Schema<"StoreSummary">;
export type StoreList = Schema<"StoreList">;

export type ScriptTemplateEntry = Schema<"ScriptTemplateEntry">;

export type ScriptTemplateCatalog = Schema<"ScriptTemplateCatalog">;

export type WorkbenchList = Schema<"WorkbenchList">;

export type ReeIndexEntryWire = Schema<"ReeIndexEntry">;

export type ReeIndexList = Schema<"ReeIndexList">;

export type PatchReeDefinitionPayload = Schema<"PatchReeDefinitionPayload">;

export type AcquireSourcePayload = Schema<"AcquireSourcePayload">;

export function toSourceAcquireRequest(input: {
  origin_url?: unknown;
  source_type?: unknown;
  revision?: unknown;
}): AcquireSourcePayload {
  const revision = typeof input.revision === "string" ? input.revision.trim() : "";
  return {
    origin_url: String(input.origin_url ?? ""),
    source_type: String(input.source_type ?? "git") as AcquireSourcePayload["source_type"],
    ...(revision ? { revision } : {}),
  };
}

export type UploadInitPayload = Schema<"UploadInitPayload">;

export type UploadInitResponse = Schema<"UploadInitResponse">;

export type RunExperimentPayload = Schema<"RunExperimentPayload">;

export type RunStatus = Schema<"RunSummary">["status"];

export type BuildExperimentEnvironmentPayload = Schema<"BuildExperimentEnvironmentPayload">;

export type GenerateSbomPayload = Schema<"GenerateSbomPayload">;

export type ObserveHardwarePayload = Schema<"ObserveHardwarePayload">;

export type CrossCheckSbomPayload = Schema<"CrossCheckSbomPayload">;

export type ActivateExperimentEnvironmentPayload = Schema<"ActivateExperimentEnvironmentPayload">;

export type EvaluateReproducibilityPayload = Schema<"EvaluateReproducibilityPayload">;

export type RunSummary = Schema<"RunSummary">;

export type RunList = Schema<"RunList">;

export type RunLogEntry = Schema<"RunLogEntry">;

export type RunLogPage = Schema<"RunLogPage">;

export type FileMutationResponse = NullableToOptional<Schema<"FileMutationResponse">>;

export type ScriptTargetSelector = Schema<"ScriptTargetSelectorPayload">;

export type InferenceReport = Schema<"InferenceReport">;

export type LintReport = Schema<"LintReport">;

export type LintFinding = Schema<"Finding">;

export type LintTierStatus = Schema<"TierStatus">;

export type LintScriptsResponse = Schema<"LintScriptsResponse">;

export type ScriptDeclarations = Schema<"ScriptDeclarations">;

export type DecisionTrace = Schema<"DecisionTrace">;

export type DecisionStep = Schema<"DecisionStep">;

export type DecisionDag = Schema<"DecisionDag">;

export type DeleteReeResponse = Schema<"DeleteReeResponse">;
