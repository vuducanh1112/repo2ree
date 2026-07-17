import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { Hbom, ReeCatalogMetadata, ReeExperiment, ReeRunnable, ReeSpec } from "./ReeSpec";

// The patch travels in the backend's wire format: the intent payload is a
// serialized Pydantic model, so its keys are snake_case. Domain types are
// camelCase; the serializers below own the conversion.
export interface ReeIntentPatch extends Record<string, unknown> {
  name: string;
  catalog_metadata: Record<string, unknown>;
  origin_url: string;
  source_type: string;
  runtime: string;
  activation: Record<string, unknown>;
  sbom: string;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  experiments: Array<Record<string, unknown>>;
  hardware_description: Record<string, unknown>;
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

function serializeRunnable(runnable: ReeRunnable): Record<string, unknown> {
  return {
    description: runnable.description,
    run_script: runnable.runScript,
    verify_script: runnable.verifyScript,
    output_paths: runnable.outputPaths,
    runtime_estimate: runnable.runtimeEstimate,
    resource_estimates: runnable.resourceEstimates,
  };
}

function serializeExperiment(experiment: ReeExperiment): Record<string, unknown> {
  return {
    name: experiment.name,
    ...serializeRunnable(experiment),
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

// The autosave patch intentionally omits `resolvedRevision` (the resolved
// commit). It is a backend-owned receipt: acquisition settles it server-side and
// source reset clears it, and no UI flow ever authors it. Serializing it would
// let a stale/blank local copy clobber the backend's on the next autosave, since
// apply_patch merges by key. (`swhid` stays below — unlike revision it has a real
// client writer, the Software Heritage archival step, so it must round-trip.)
export function toReePatchFromSlices({ reeSpec }: ReePatchSlices): ReeIntentPatch {
  return {
    name: reeSpec.name || "",
    catalog_metadata: serializeCatalogMetadata(reeSpec.catalogMetadata),
    origin_url: reeSpec.originUrl || "",
    source_type: reeSpec.sourceType || "",
    runtime: reeSpec.runtime || "",
    activation: serializeRunnable(reeSpec.activation),
    sbom: reeSpec.sbom || "",
    swhid: reeSpec.swhid || "",
    zenodo_doi: reeSpec.zenodoDoi || "",
    dataverse_doi: reeSpec.dataverseDoi || "",
    experiments: (reeSpec.experiments || []).map(serializeExperiment),
    hardware_description: serializeHbom(reeSpec.hardwareDescription),
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
      zenodoDoi: ree.zenodoDoi,
      dataverseDoi: ree.dataverseDoi,
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
