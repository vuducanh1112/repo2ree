import { PAGE } from "../../../../../../application/state/pages";
import { hbomHasAnyComponents } from "../../../../../../domain/hbom/HbomSummary";
import type { Badges } from "../../../../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../../../../domain/ree/ReeViewState";

interface SealCableItem {
  key: string;
  label: string;
  live: boolean;
}

export function buildSealCableItems(ree: ReeViewState, badges: Badges): SealCableItem[] {
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
    { key: "runtime", label: "Runtime", live: !!ree.runtimeIncluded },
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
