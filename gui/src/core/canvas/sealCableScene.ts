import { PAGE } from "../app-shell/pages";
import { hbomHasAnyComponents } from "../hbom/HbomSummary";
import { isAuditCurrent } from "../ree/StepEvidence";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";

interface SealCableItem {
  key: string;
  label: string;
  live: boolean;
}

export function buildSealCableItems(ree: ReeEditorViewModel): SealCableItem[] {
  return [
    {
      key: PAGE.METADATA,
      label: "Metadata",
      live: !!ree.spec.name,
    },
    {
      key: PAGE.HBOM,
      label: "HBOM",
      live: hbomHasAnyComponents(ree.spec.hardwareDescription),
    },
    { key: PAGE.SOURCE, label: "Source", live: !!ree.source.sourceAvailable },
    {
      key: "runtime",
      label: "Runtime",
      live: !!ree.spec.runtime?.trim() && ree.spec.runtime !== "__skipped__",
    },
    // "Source identity", not "Software Heritage": the SWHID is computed locally
    // from the acquired tree and asserts nothing about any archive holding it.
    { key: "swh", label: "Source identity", live: !!ree.spec.swhid },
    { key: "sbom", label: "SBOM", live: !!ree.spec.sbom },
    {
      key: "evaluate",
      label: "Reproducibility Readiness",
      live: isAuditCurrent(ree.audit, "evaluation"),
    },
    // Never live until deposits are read back from archive-binding attestations;
    // nothing on the spec can stand in for "an archive accepted this bundle".
    { key: "archive", label: "Archival & DOIs", live: false },
    {
      key: "activation",
      label: "Test Activation",
      live: isAuditCurrent(ree.audit, "test_activation"),
    },
  ];
}

export type { SealCableItem };
