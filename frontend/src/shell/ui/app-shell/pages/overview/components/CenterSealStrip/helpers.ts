import { hbomHasAnyComponents } from "../../../../../../../core/hbom/HbomSummary";
import type { Badges } from "../../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../../core/ree-editor/reeEditorViewModel";
import { PAGE } from "../../../../state/pages";

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
      live: hbomHasAnyComponents(ree.hardware_description),
    },
    { key: PAGE.SOURCE, label: "Source", live: !!ree.sourceAvailable },
    {
      key: "runtime",
      label: "Runtime",
      live: !!ree.runtime?.trim() && ree.runtime !== "__skipped__",
    },
    { key: "swh", label: "Software Heritage", live: !!ree.swhid },
    { key: "sbom", label: "SBOM", live: !!ree.sbom },
    { key: "evaluate", label: "Evaluate", live: !!badges?.evaluate },
    {
      key: "archive",
      label: "Archival & DOIs",
      live: !!(ree.zenodo_doi || ree.dataverse_doi),
    },
    {
      key: "activation",
      label: "Test Activation",
      live: !!badges?.activation,
    },
  ];
}

export type { SealCableItem };
