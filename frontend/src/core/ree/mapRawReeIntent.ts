import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import { normalizeHBOM } from "../hbom/HbomSummary";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import {
  type ContainerEngine,
  createEmptyExperimentResourceEstimates,
  createEmptyReeActivation,
  createEmptyReeCatalogMetadata,
  createEmptyReeExperiment,
  createEmptyRuntimeEntry,
  type ExpectedOutput,
  type ReeActivation,
  type ReeCatalogMetadata,
  type ReeContributor,
  type ReeExperiment,
  type ReeSpec,
  type RuntimeEntry,
} from "./ReeSpec";
import { CONTAINER_ENGINES } from "./runtimeEntryLabels";

// ================================================
// Types
// ================================================

interface MapRawReeIntentToReeOptions {
  reeIntent: Record<string, unknown> | null | undefined;
  reeSession?: Record<string, unknown> | null | undefined;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export interface RawReeIntentSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

// ================================================
// Helpers
// ================================================

function mapRawCatalogMetadata(value: unknown): ReeCatalogMetadata {
  const metadata = value && typeof value === "object" ? (value as Record<string, unknown>) : {};

  const contributors: ReeContributor[] = Array.isArray(metadata.contributors)
    ? metadata.contributors.map((entry) => {
        const item = (entry as Record<string, unknown>) || {};
        return {
          identifier: String(item.identifier ?? ""),
          name: String(item.name ?? ""),
          affiliation_name: String(item.affiliation_name ?? ""),
          affiliation_identifier: String(item.affiliation_identifier ?? ""),
        };
      })
    : [];

  return {
    ...createEmptyReeCatalogMetadata(),
    description: String(metadata.description ?? ""),
    version: String(metadata.version ?? ""),
    website: String(metadata.website ?? ""),
    keywords: Array.isArray(metadata.keywords)
      ? metadata.keywords.map((keyword) => String(keyword))
      : [],
    contributors,
    corresponding_author_identifier: metadata.corresponding_author_identifier
      ? String(metadata.corresponding_author_identifier)
      : null,
  };
}

function mapRawResourceEstimates(value: unknown): ReeExperiment["resource_estimates"] {
  const estimates = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    ...createEmptyExperimentResourceEstimates(),
    cpu: String(estimates.cpu ?? ""),
    memory: String(estimates.memory ?? ""),
    gpu: String(estimates.gpu ?? ""),
    storage: String(estimates.storage ?? ""),
    network: String(estimates.network ?? ""),
  };
}

function mapRawActivation(value: unknown): ReeActivation {
  const raw = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    ...createEmptyReeActivation(),
    description: String(raw.description ?? ""),
    command: String(raw.command ?? ""),
    runtime_estimate: String(raw.runtime_estimate ?? ""),
    resource_estimates: mapRawResourceEstimates(raw.resource_estimates),
    ...(Array.isArray(raw.outputs) && raw.outputs.length > 0
      ? { outputs: raw.outputs as ExpectedOutput[] }
      : {}),
  };
}

// Wire values are untrusted: validate rather than cast, so a malformed engine,
// non-object env, or non-numeric cpu can't masquerade as a well-typed entry.
function asContainerEngine(value: unknown): ContainerEngine {
  return CONTAINER_ENGINES.includes(value as ContainerEngine)
    ? (value as ContainerEngine)
    : "docker";
}

function asStringMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    out[k] = String(v ?? "");
  }
  return out;
}

function asPositiveInt(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

function mapRawRuntimeEntry(value: unknown): RuntimeEntry {
  const raw = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  switch (raw.kind) {
    case "container":
      return {
        kind: "container",
        engine: asContainerEngine(raw.engine),
        workdir: String(raw.workdir ?? "/workspace"),
        env: asStringMap(raw.env),
        gpus: Boolean(raw.gpus ?? false),
        activate: String(raw.activate ?? ""),
        enter_script: String(raw.enter_script ?? ""),
      };
    case "local":
      return {
        kind: "local",
        activate: String(raw.activate ?? ""),
        enter_script: String(raw.enter_script ?? ""),
      };
    case "vm":
      return {
        kind: "vm",
        cpu: asPositiveInt(raw.cpu, 1),
        memory: String(raw.memory ?? "4G"),
        ssh_host: String(raw.ssh_host ?? ""),
        ssh_user: String(raw.ssh_user ?? ""),
        ssh_key: String(raw.ssh_key ?? ""),
        activate: String(raw.activate ?? ""),
        enter_script: String(raw.enter_script ?? ""),
      };
    case "custom":
      return {
        kind: "custom",
        enter_script: String(raw.enter_script ?? ""),
        activate: String(raw.activate ?? ""),
      };
    default:
      return createEmptyRuntimeEntry();
  }
}

// ================================================
// Mapper
// ================================================

export function mapRawReeIntentToSlices({
  reeIntent,
  reeSession,
  fallbackName,
  fallbackOriginUrl = "",
}: MapRawReeIntentToReeOptions): RawReeIntentSlices {
  const intent = reeIntent || {};
  const session = reeSession || {};

  const experiments: ReeExperiment[] = Array.isArray(intent.experiments)
    ? intent.experiments.map((entry) => {
        const item = (entry as Record<string, unknown>) || {};
        return {
          ...createEmptyReeExperiment(),
          name: String(item.name ?? ""),
          description: String(item.description ?? ""),
          command: String(item.command ?? ""),
          runtime_estimate: String(item.runtime_estimate ?? ""),
          resource_estimates: mapRawResourceEstimates(item.resource_estimates),
          ...(Array.isArray(item.outputs) && item.outputs.length > 0
            ? { outputs: item.outputs as ExpectedOutput[] }
            : {}),
        };
      })
    : [];

  return {
    reeSpec: {
      name: String(intent.name ?? fallbackName ?? ""),
      catalog_metadata: mapRawCatalogMetadata(intent.catalog_metadata),
      origin_url: String(intent.origin_url ?? fallbackOriginUrl ?? ""),
      source_type: (intent.source_type as ReeSpec["source_type"]) || "",
      runtime: String(intent.runtime ?? ""),
      runtime_entry: mapRawRuntimeEntry(intent.runtime_entry),
      build_runtime_script: String(intent.build_runtime_script ?? ""),
      activation: mapRawActivation(intent.activation),
      sbom: String(intent.sbom ?? ""),
      swhid: String(intent.swhid ?? ""),
      zenodo_doi: intent.zenodo_doi ? String(intent.zenodo_doi) : undefined,
      dataverse_doi: intent.dataverse_doi ? String(intent.dataverse_doi) : undefined,
      experiments,
      hardware_description: normalizeHBOM(intent.hardware_description),
    },
    workspaceSourceState: {
      sourceAvailable: Boolean(session.source_available),
      sourceIncluded: Boolean(session.source_included),
      sourceAcquiredBy:
        (session.source_acquired_by as WorkspaceSourceState["sourceAcquiredBy"]) || undefined,
      uploadedArchive: session.uploaded_archive ? String(session.uploaded_archive) : undefined,
      sourceSnapshotArchive: session.source_snapshot_archive
        ? String(session.source_snapshot_archive)
        : undefined,
      sourceSnapshotCapturedAt: session.source_snapshot_captured_at
        ? String(session.source_snapshot_captured_at)
        : undefined,
    },
    artifactStatus: {
      runtimeIncluded: Boolean(session.runtime_included),
      sealedAt: session.sealed_at ? String(session.sealed_at) : undefined,
      sealHash: session.seal_hash ? String(session.seal_hash) : undefined,
    },
    evaluationState: {
      dependencyLevel: Number(session.dependency_level ?? 0),
      environmentLevel: Number(session.environment_level ?? 0),
      machineLevel: Number(session.machine_level ?? 0),
      detectedDependencies: session.detected_dependencies
        ? String(session.detected_dependencies)
        : undefined,
    },
  };
}
