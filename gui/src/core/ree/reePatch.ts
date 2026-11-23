import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import { bytesFromGib, mbpsFromGbps } from "../hbom/hbomUnits";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { Hbom, ReeCatalogMetadata, ReeExperiment, ReeSpec } from "./ReeSpec";

export interface ReeIntentPatch extends Record<string, unknown> {
  name: string;
  catalog: Record<string, unknown>;
  experiment_environment: Record<string, unknown>;
  experiments: Array<Record<string, unknown>>;
  hbom: Record<string, unknown>;
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
    run_script_path: experiment.runScript || null,
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
      Object.fromEntries(
        Object.entries(device).map(([key, value]) => {
          const unit = DEVICE_WIRE_UNITS[key];
          return unit ? [unit.field, unit.convert(value)] : [fields[key] ?? key, value];
        }),
      ),
    ]),
  );
}

const DEVICE_WIRE_UNITS: Record<string, { field: string; convert: (value: unknown) => number }> = {
  memoryGb: { field: "memory_bytes", convert: bytesFromGib },
  capacityGb: { field: "capacity_bytes", convert: bytesFromGib },
  bandwidthGbps: { field: "bandwidth_mbps", convert: mbpsFromGbps },
};

const DEVICE_WIRE_FIELDS: Record<string, string> = {
  coresPerCpu: "cores_per_cpu",
  threadsPerCore: "threads_per_core",
  memoryType: "memory_type",
  speedMtS: "speed_mt_s",
  storageType: "storage_type",
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

export function toReePatchFromSlices({ reeSpec }: ReePatchSlices): ReeIntentPatch {
  return {
    name: reeSpec.name || "",
    catalog: serializeCatalogMetadata(reeSpec.catalogMetadata),
    experiment_environment: { artifact_path: reeSpec.experimentEnvironmentPath || null },
    experiments: (reeSpec.experiments || []).map(serializeExperiment),
    hbom: serializeHbom(reeSpec.hbom),
  };
}
