import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import type { ReeDocument } from "../../infra/api/apiTypes";

export function mapReeDetailToReeSlices(ree: ReeDocument) {
  const subject = ree.ree.subject;
  const definition = subject?.definition;
  const receipts = subject?.receipts;
  const source = definition?.source;
  const sourceReceipt = receipts?.source;
  const activation = definition?.test_activation;
  const levels = ree.assessment.reproducibility;

  return mapRawReeIntentToSlices({
    reeIntent: {
      name: definition?.name ?? "",
      catalog_metadata: definition?.catalog,
      origin_url: source?.origin_url,
      source_type: source?.source_type,
      revision: sourceReceipt?.resolved_revision ?? source?.requested_ref,
      runtime: definition?.runtime?.runtime_path,
      activation: activation
        ? {
            run_script: activation.run_script_path,
            verify_script: activation.verify_script_path,
          }
        : undefined,
      sbom: receipts?.sbom?.sbom_path,
      swhid: sourceReceipt?.observed_swhid,
      experiments: (definition?.experiments ?? []).map((experiment) => ({
        name: experiment.name,
        run_script: experiment.run_script_path,
        verify_script: experiment.verify_script_path,
        output_paths: experiment.output_paths,
      })),
      hardware_description: definition?.hardware,
    },
    reeSession: {
      source_available: ree.assessment.source.payload === "present",
      source_included: ree.status === "sealed" && ree.assessment.source.payload === "present",
      runtime_included: ree.status === "sealed" && ree.assessment.runtime.payload === "present",
      sealed_at: ree.ree.seal?.sealed_at,
      seal_hash: ree.ree.seal?.ree_digest,
      dependency_level: levels?.dependency ?? 0,
      environment_level: levels?.environment ?? 0,
      machine_level: levels?.machine ?? 0,
    },
    fallbackName: definition?.name ?? "",
    fallbackOriginUrl: source?.origin_url ?? "",
  });
}
