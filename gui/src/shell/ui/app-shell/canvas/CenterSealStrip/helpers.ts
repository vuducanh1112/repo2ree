import { PAGE } from "@core/app-shell/pages";
import { hbomHasAnyComponents } from "@core/hbom/HbomSummary";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";

interface SealCableItem {
  key: string;
  label: string;
  live: boolean;
}

export function buildSealCableItems(ree: ReeEditorViewModel, badges: Badges): SealCableItem[] {
  return [
    {
      key: PAGE.METADATA,
      label: "Metadata",
      live: !!ree.name,
    },
    {
      key: PAGE.HBOM,
      label: "HBOM",
      live: hbomHasAnyComponents(ree.hardwareDescription),
    },
    { key: PAGE.SOURCE, label: "Source", live: !!ree.sourceAvailable },
    {
      key: "runtime",
      label: "Runtime",
      live: !!ree.runtime?.trim() && ree.runtime !== "__skipped__",
    },
    // "Source identity", not "Software Heritage": the SWHID is computed locally
    // from the acquired tree and asserts nothing about any archive holding it.
    { key: "swh", label: "Source identity", live: !!ree.swhid },
    { key: "sbom", label: "SBOM", live: !!ree.sbom },
    { key: "evaluate", label: "Reproducibility Readiness", live: !!badges?.evaluate },
    // Never live until deposits are read back from archive-binding attestations;
    // nothing on the spec can stand in for "an archive accepted this bundle".
    { key: "archive", label: "Archival & DOIs", live: false },
    {
      key: "activation",
      label: "Test Activation",
      live: !!badges?.activation,
    },
  ];
}

export type { SealCableItem };
