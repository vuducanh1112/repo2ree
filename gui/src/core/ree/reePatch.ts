import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { Hbom, ReeCatalogMetadata, ReeExperiment, ReeSpec } from "./ReeSpec";

// The editor still uses its UI-oriented ReeSpec, while this serializer owns
// the conversion to the portable definition's wire shape.
export interface ReeIntentPatch extends Record<string, unknown> {
  name: string;
  catalog: Record<string, unknown>;
  source?: Record<string, unknown>;
  build_runtime: Record<string, unknown>;
  experiments: Array<Record<string, unknown>>;
  hardware: Record<string, unknown>;
}

interface ReePatchSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

function serializeCatalogMetadata(metadata: ReeCatalogMetadata): Record<string, unknown> {
  return {
    description: metadata.description,
    version: metadata.version,
    website: metadata.website,
    keywords: metadata.keywords,
    contributors: metadata.contributors.map((contributor) => ({
      identifier: contributor.identifier,
      name: contributor.name,
      affiliation_name: contributor.affiliationName,
      affiliation_identifier: contributor.affiliationIdentifier,
    })),
    corresponding_author_identifier: metadata.correspondingAuthorIdentifier,
  };
}

function serializeExperiment(experiment: ReeExperiment): Record<string, unknown> {
  return {
    name: experiment.name,
    output_paths: experiment.outputPaths,
  };
}

function serializeDeviceMap(
  devices: Record<string, Record<string, unknown>>,
  fields: Record<string, string>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(devices).map(([model, device]) => [
      model,
      Object.fromEntries(Object.entries(device).map(([key, value]) => [fields[key] ?? key, value])),
    ]),
  );
}

const DEVICE_WIRE_FIELDS: Record<string, string> = {
  coresPerCpu: "cores_per_cpu",
  threadsPerCore: "threads_per_core",
  memoryGb: "memory_gb",
  capacityGb: "capacity_gb",
  memoryType: "memory_type",
  speedMtS: "speed_mt_s",
  storageType: "storage_type",
  bandwidthGbps: "bandwidth_gbps",
  networkType: "network_type",
  extraInfo: "extra_info",
};

function serializeHbom(hbom: Hbom): Record<string, unknown> {
  const asDeviceMap = (value: unknown) =>
    serializeDeviceMap(value as Record<string, Record<string, unknown>>, DEVICE_WIRE_FIELDS);
  return {
    cpus: asDeviceMap(hbom.cpus),
    gpus: asDeviceMap(hbom.gpus),
    memory: asDeviceMap(hbom.memory),
    storage: asDeviceMap(hbom.storage),
    network: asDeviceMap(hbom.network),
    extra_info: hbom.extraInfo,
  };
}

// Autosave intentionally omits the source identity fields `resolvedRevision`
// and `swhid`. Acquisition settles both server-side and source reset clears
// both there; serializing a stale/blank local copy would let an unrelated editor
// save clobber evidence the backend just computed, since apply_patch merges by
// key. Local state still carries them for display after authoritative hydration.
export function toReePatchFromSlices({ reeSpec }: ReePatchSlices): ReeIntentPatch {
  return {
    name: reeSpec.name || "",
    catalog: serializeCatalogMetadata(reeSpec.catalogMetadata),
    // Omitted, never nulled, when nothing is authored locally. The patch merges
    // by key, and an upload declares its source server-side (acquisition names
    // the type from the archive), so a `source: null` here would erase a
    // declaration the editor never held — leaving the acquisition receipt
    // describing a source the REE no longer declares. Removing a source is its
    // own explicit operation, not something autosave decides.
    ...(reeSpec.sourceType
      ? {
          source: {
            origin_url: reeSpec.originUrl || null,
            source_type: reeSpec.sourceType,
            requested_ref: null,
          },
        }
      : {}),
    // The runtime destination rides on the build recipe, not beside it: the
    // script and what it produces are one declaration (as with an experiment's
    // output_paths). Sending only this key is safe — the backend rehydrates the
    // script's identity from the reserved overlay file, which every REE is
    // seeded with, and carries the declared path through. An undeclared path is
    // sent as null so clearing the field clears the declaration; the recipe
    // itself is never nulled, since dropping it would discard the build script
    // the REE already owns.
    build_runtime: { runtime_path: reeSpec.runtime || null },
    experiments: (reeSpec.experiments || []).map(serializeExperiment),
    hardware: serializeHbom(reeSpec.hardwareDescription),
  };
}

export function toReePatch(
  ree: ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState,
): ReeIntentPatch {
  return toReePatchFromSlices({
    reeSpec: {
      name: ree.name,
      catalogMetadata: ree.catalogMetadata,
      originUrl: ree.originUrl,
      sourceType: ree.sourceType,
      resolvedRevision: ree.resolvedRevision,
      runtime: ree.runtime,
      activation: ree.activation,
      sbom: ree.sbom,
      swhid: ree.swhid,
      experiments: ree.experiments || [],
      hardwareDescription: ree.hardwareDescription,
    },
    workspaceSourceState: {
      sourceAvailable: ree.sourceAvailable,
      sourceIncluded: ree.sourceIncluded,
      sourceAcquiredBy: ree.sourceAcquiredBy,
      uploadedArchive: ree.uploadedArchive,
      sourceSnapshotArchive: ree.sourceSnapshotArchive,
      sourceSnapshotCapturedAt: ree.sourceSnapshotCapturedAt,
    },
    artifactStatus: {
      runtimeIncluded: ree.runtimeIncluded,
      sealedAt: ree.sealedAt,
      sealHash: ree.sealHash,
    },
    evaluationState: {
      dependencyLevel: ree.dependencyLevel,
      environmentLevel: ree.environmentLevel,
      machineLevel: ree.machineLevel,
    },
  });
}
