import { hbomHasAnyComponents } from "../../../../../core/hbom/HbomSummary";
import type { Badges } from "../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import { PAGE } from "../../state/pages";

type PodCableSide = "left" | "right" | "top";

interface PodCableState {
  id: string;
  label: string;
  side: PodCableSide;
  podSide: PodCableSide;
  podRank: number;
  color: string;
  shadow: string;
  connected: boolean;
}

export function getPodCableStates(ree: ReeEditorViewModel, badges: Badges): PodCableState[] {
  const hasName = !!ree.name?.trim();
  const fieldsConnected = hasName;
  const hbomConnected = hbomHasAnyComponents(ree.hardware_description);

  const archiveConnected = !!(ree.zenodo_doi || ree.dataverse_doi);
  const activationConnected = !!badges?.activation;
  const sourceConnected = !!ree.sourceAvailable;
  const runtimeConnected = !!ree.runtimeIncluded;
  const sbomConnected = !!ree.sbom?.trim();
  const swhConnected = !!ree.swhid?.trim();
  const evaluateConnected = !!badges?.evaluate;
  const sealConnected = !!ree.sealedAt;

  return [
    {
      id: PAGE.SOURCE,
      label: "Source",
      side: "right",
      podSide: "left",
      podRank: 1,
      color: "#f59e0b",
      shadow: "#92400e",
      connected: sourceConnected,
    },
    {
      id: "runtime",
      label: "Runtime",
      side: "right",
      podSide: "left",
      podRank: 4,
      color: "#0891b2",
      shadow: "#164e63",
      connected: runtimeConnected,
    },
    {
      id: "sbom",
      label: "SBOM",
      side: "right",
      podSide: "left",
      podRank: 5,
      color: "#16a34a",
      shadow: "#14532d",
      connected: sbomConnected,
    },
    {
      id: "fields",
      label: "Fields",
      side: "right",
      podSide: "left",
      podRank: 2,
      color: "#22c55e",
      shadow: "#166534",
      connected: fieldsConnected,
    },
    {
      id: PAGE.HBOM,
      label: "HBOM",
      side: "right",
      podSide: "left",
      podRank: 3,
      color: "#0f766e",
      shadow: "#134e4a",
      connected: hbomConnected,
    },
    {
      id: "archive",
      label: "Archive",
      side: "left",
      podSide: "right",
      podRank: 3,
      color: "#e4572e",
      shadow: "#7c2d12",
      connected: archiveConnected,
    },
    {
      id: "activation",
      label: "Activation",
      side: "left",
      podSide: "right",
      podRank: 4,
      color: "#7c3aed",
      shadow: "#3b0764",
      connected: activationConnected,
    },
    {
      id: "swh",
      label: "SWH",
      side: "left",
      podSide: "right",
      podRank: 1,
      color: "#e4572e",
      shadow: "#7c2d12",
      connected: swhConnected,
    },
    {
      id: "evaluate",
      label: "Evaluate",
      side: "left",
      podSide: "right",
      podRank: 2,
      color: "#7c3aed",
      shadow: "#3b0764",
      connected: evaluateConnected,
    },
    {
      id: "seal",
      label: "Seal",
      side: "top",
      podSide: "top",
      podRank: 1,
      color: "#f59e0b",
      shadow: "#78350f",
      connected: sealConnected,
    },
  ];
}
