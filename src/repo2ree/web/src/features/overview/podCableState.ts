import { PAGE } from "../../constants/pages";
import type { Badges, Ree } from "../../types";

export type PodCableSide = "left" | "right" | "top";

export interface PodCableState {
  id: string;
  label: string;
  side: PodCableSide;
  podSide: PodCableSide;
  podRank: number;
  color: string;
  shadow: string;
  connected: boolean;
}

export function getPodCableStates(ree: Ree, badges: Badges): PodCableState[] {
  const fieldsConnected =
    (["name", "origin_url", "runtime", "build_runtime_script"] as const).filter(
      (fieldKey) => !!ree[fieldKey],
    ).length >= 2;

  const archiveConnected = !!(ree.zenodo_doi || ree.dataverse_doi);
  const activationConnected = !!badges?.activation;
  const sourceConnected = !!ree._sourceAvailable;
  const runtimeConnected = !!ree._runtimeIncluded;
  const sbomConnected = !!ree.sbom?.trim();
  const swhConnected = !!ree.swhid?.trim();
  const evaluateConnected = !!badges?.evaluate;
  const sealConnected = !!ree._sealedAt;

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
      podRank: 3,
      color: "#0891b2",
      shadow: "#164e63",
      connected: runtimeConnected,
    },
    {
      id: "sbom",
      label: "SBOM",
      side: "right",
      podSide: "left",
      podRank: 4,
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
