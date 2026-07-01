import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { ReeActivation, ReeCatalogMetadata, ReeExperiment, ReeSpec } from "./ReeSpec";

export interface ReeIntentPatch extends Record<string, unknown> {
  name: string;
  catalog_metadata: ReeCatalogMetadata;
  origin_url: string;
  source_type: string;
  runtime: string;
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

// The autosave patch intentionally omits `resolvedRevision` (the resolved
// commit). It is a backend-owned receipt: acquisition settles it server-side and
// source reset clears it, and no UI flow ever authors it. Serializing it would
// let a stale/blank local copy clobber the backend's on the next autosave, since
// apply_patch merges by key. (`swhid` stays below — unlike revision it has a real
// client writer, the Software Heritage archival step, so it must round-trip.)
export function toReePatchFromSlices({ reeSpec }: ReePatchSlices): ReeIntentPatch {
  return {
    name: reeSpec.name || "",
    catalog_metadata: reeSpec.catalog_metadata,
    origin_url: reeSpec.origin_url || "",
    source_type: reeSpec.source_type || "",
    runtime: reeSpec.runtime || "",
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
      resolvedRevision: ree.resolvedRevision,
      runtime: ree.runtime,
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
