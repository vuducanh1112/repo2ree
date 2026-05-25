import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { HBOM, ReeCatalogMetadata, ReeExperiment, ReeSpec } from "./ReeSpec";

interface ReePatch extends Record<string, unknown> {
  name: string;
  catalog_metadata: ReeCatalogMetadata;
  origin_url: string;
  source_type: string;
  runtime: string;
  build_runtime_script: string;
  activation_script: string;
  sbom: string;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  detected_dependencies: string;
  experiments: ReeExperiment[];
  hardware_description: HBOM;
  source_included: boolean;
  runtime_included: boolean;
}

interface ReePatchSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

export function toReePatchFromSlices({
  reeSpec,
  workspaceSourceState,
  artifactStatus,
}: ReePatchSlices): ReePatch {
  return {
    name: reeSpec.name || "",
    catalog_metadata: reeSpec.catalog_metadata,
    origin_url: reeSpec.origin_url || "",
    source_type: reeSpec.source_type || "",
    runtime: reeSpec.runtime || "",
    build_runtime_script: reeSpec.build_runtime_script || "",
    activation_script: reeSpec.activation_script || "",
    sbom: reeSpec.sbom || "",
    swhid: reeSpec.swhid || "",
    zenodo_doi: reeSpec.zenodo_doi || "",
    dataverse_doi: reeSpec.dataverse_doi || "",
    detected_dependencies: reeSpec.detected_dependencies || "",
    experiments: reeSpec.experiments || [],
    hardware_description: reeSpec.hardware_description || {},
    source_included: !!workspaceSourceState.sourceIncluded,
    runtime_included: !!artifactStatus.runtimeIncluded,
  };
}

export function toReePatch(
  ree: ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState,
): ReePatch {
  return toReePatchFromSlices({
    reeSpec: {
      name: ree.name,
      catalog_metadata: ree.catalog_metadata,
      origin_url: ree.origin_url,
      source_type: ree.source_type,
      runtime: ree.runtime,
      build_runtime_script: ree.build_runtime_script,
      activation_script: ree.activation_script,
      sbom: ree.sbom,
      swhid: ree.swhid,
      zenodo_doi: ree.zenodo_doi,
      dataverse_doi: ree.dataverse_doi,
      detected_dependencies: ree.detected_dependencies,
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
      downloadableFiles: ree.downloadableFiles,
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
