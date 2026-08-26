import { mapRawReeIntentToSlices } from "@core/ree/mapRawReeIntent";
import type { ReeDocument } from "../../infra/api/apiTypes";

export function mapReeDetailToReeSlices(ree: ReeDocument) {
  const subject = ree.ree.subject;
  const definition = subject?.definition;
  const receipts = subject?.receipts;
  const source = definition?.source;
  const sourceReceipt = receipts?.source;
  const activation = definition?.test_activation;
  // The axes are evaluate's own finding, so they are read from the receipt that
  // recorded them rather than from the audit, which reports evidence and nothing else.
  const evaluation = receipts?.evaluation;

  return mapRawReeIntentToSlices({
    // The audit is the REE's own word on whether each receipt still holds; the
    // shell reads step doneness from it rather than from what this tab ran.
    audit: ree.audit,
    reeIntent: {
      name: definition?.name ?? "",
      catalog_metadata: definition?.catalog,
      origin_url: source?.origin_url,
      source_type: source?.source_type,
      revision: sourceReceipt?.resolved_revision ?? source?.requested_ref,
      runtime: definition?.build_runtime?.runtime_path,
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
      // Payload speaks for a sealed bundle's inventory and nothing else — a
      // draft's reads not_applicable by construction. Whether the workspace
      // holds a source is what the acquisition receipt's standing says, so ask
      // evidence: `current` means the REE still declares the source it acquired.
      source_available: ree.audit.source.evidence === "current",
      source_included: ree.status === "sealed" && ree.audit.source.payload === "present",
      runtime_included: ree.status === "sealed" && ree.audit.runtime.payload === "present",
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
