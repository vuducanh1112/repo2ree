import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import type { ReeDocument } from "../../infra/api/apiTypes";

export function mapReeDetailToReeSlices(ree: ReeDocument) {
  const subject = ree.ree.subject;
  const definition = subject?.definition;
  const receipts = subject?.receipts;
  const source = definition?.source;
  const sourceReceipt = receipts?.acquire_source;
  const evaluation = receipts?.evaluate_reproducibility;

  return mapRawReeIntentToSlices({
    audit: ree.audit,
    steps: ree.steps,
    reeIntent: {
      name: definition?.name ?? "",
      catalog_metadata: definition?.catalog,
      origin_url: source?.origin_url,
      source_type: source?.source_type,
      revision: sourceReceipt?.resolved_revision ?? source?.requested_ref,
      experiment_environment_path: definition?.experiment_environment?.artifact_path,
      sbom: receipts?.generate_sbom?.sbom_path,
      swhid: sourceReceipt?.observed_swhid,
      experiments: (definition?.experiments ?? []).map((experiment) => ({
        name: experiment.name,
        run_script: experiment.run_script_path,
        verify_script: experiment.verify_script_path,
        output_paths: experiment.output_paths,
      })),
      hbom: definition?.hbom,
    },
    reeSession: {
      source_available: ree.audit.acquire_source.evidence === "current",
      source_included: ree.status === "sealed" && ree.audit.acquire_source.payload === "present",
      experiment_environment_included:
        ree.status === "sealed" && ree.audit.build_experiment_environment.payload === "present",
      sealed_at: ree.ree.seal?.sealed_at,
      seal_hash: ree.ree.seal?.ree_digest,
      dependency_level: evaluation?.dependency_level ?? 0,
      environment_level: evaluation?.environment_level ?? 0,
      machine_level: evaluation?.machine_level ?? 0,
    },
    fallbackName: definition?.name ?? "",
    fallbackOriginUrl: source?.origin_url ?? "",
  });
}
