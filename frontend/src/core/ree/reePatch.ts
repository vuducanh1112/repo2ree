import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type {
  ReeActivation,
  ReeCatalogMetadata,
  ReeExperiment,
  ReeSpec,
  RuntimeEntry,
} from "./ReeSpec";

export interface ReeIntentPatch extends Record<string, unknown> {
  name: string;
  catalog_metadata: ReeCatalogMetadata;
  origin_url: string;
  source_type: string;
  runtime: string;
  runtime_entry: RuntimeEntry;
  build_runtime_script: string;
  activation: ReeActivation;
  sbom: string;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  experiments: ReeExperiment[];
  hardware_description: Record<string, unknown>;
}

interface ReePatchSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

export function toReePatchFromSlices({ reeSpec }: ReePatchSlices): ReeIntentPatch {
  return {
    name: reeSpec.name || "",
    catalog_metadata: reeSpec.catalog_metadata,
    origin_url: reeSpec.origin_url || "",
    source_type: reeSpec.source_type || "",
    runtime: reeSpec.runtime || "",
    runtime_entry: reeSpec.runtime_entry,
    build_runtime_script: reeSpec.build_runtime_script || "",
    activation: reeSpec.activation,
    sbom: reeSpec.sbom || "",
    swhid: reeSpec.swhid || "",
    zenodo_doi: reeSpec.zenodo_doi || "",
    dataverse_doi: reeSpec.dataverse_doi || "",
    experiments: reeSpec.experiments || [],
    hardware_description: (reeSpec.hardware_description || {}) as unknown as Record<
      string,
      unknown
    >,
  };
}

export function toReePatch(
  ree: ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState,
): ReeIntentPatch {
  return toReePatchFromSlices({
    reeSpec: {
      name: ree.name,
      catalog_metadata: ree.catalog_metadata,
      origin_url: ree.origin_url,
      source_type: ree.source_type,
      runtime: ree.runtime,
      runtime_entry: ree.runtime_entry,
      build_runtime_script: ree.build_runtime_script,
      activation: ree.activation,
      sbom: ree.sbom,
      swhid: ree.swhid,
      zenodo_doi: ree.zenodo_doi,
      dataverse_doi: ree.dataverse_doi,
      experiments: ree.experiments || [],
      hardware_description: ree.hardware_description,
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
