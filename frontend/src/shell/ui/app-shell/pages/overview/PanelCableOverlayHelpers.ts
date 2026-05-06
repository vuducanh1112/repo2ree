import type React from "react";
import type { Badges } from "../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import { getPodCableStates } from "./podCableState";

export interface Cable {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  shadow: string;
  connected: boolean;
}

export interface CableGeo {
  cables: Cable[];
  decoCables: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }>;
  w: number;
  h: number;
}

interface DecoAnchor {
  id: string;
  angle: number;
  dist: number;
}

const DECO_ANCHORS: DecoAnchor[] = [
  { id: "d1", angle: -135, dist: 380 },
  { id: "d2", angle: -45, dist: 370 },
  { id: "d3", angle: 22, dist: 340 },
  { id: "d4", angle: 68, dist: 355 },
  { id: "d5", angle: 112, dist: 345 },
  { id: "d6", angle: 158, dist: 360 },
  { id: "d7", angle: 202, dist: 375 },
  { id: "d8", angle: 248, dist: 350 },
  { id: "d9", angle: 292, dist: 365 },
  { id: "d10", angle: 337, dist: 355 },
];

type PanelCableSide = "left" | "right" | "top";

interface PanelCableSpec {
  id: string;
  ref: React.RefObject<HTMLDivElement>;
  side: PanelCableSide;
  color: string;
  shadow: string;
  connected: boolean;
}

interface PanelRefs {
  sourceRef: React.RefObject<HTMLDivElement>;
  runtimeRef: React.RefObject<HTMLDivElement>;
  metadataRef: React.RefObject<HTMLDivElement>;
  hbomRef: React.RefObject<HTMLDivElement>;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  sbomRef: React.RefObject<HTMLDivElement>;
  sealRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
}

function svgPtToContainer(
  svg: SVGSVGElement,
  container: HTMLElement,
  px: number,
  py: number,
): { x: number; y: number } | null {
  const ctm = svg.getScreenCTM();
  if (!ctm) return null;
  const cRect = container.getBoundingClientRect();
  return {
    x: ctm.a * px + ctm.c * py + ctm.e - cRect.left,
    y: ctm.b * px + ctm.d * py + ctm.f - cRect.top,
  };
}

export function cablePath(x1: number, y1: number, x2: number, y2: number): string {
  const dx = x2 - x1;
  const len = Math.hypot(dx, y2 - y1);
  const droop = len * 0.13;
  const cx1 = x1 + dx * 0.42;
  const cy1 = y1 + droop * 0.6;
  const cx2 = x2 - dx * 0.42;
  const cy2 = y2 + droop * 0.4;
  return `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
}

export function cableHl(x1: number, y1: number, x2: number, y2: number): string {
  const dx = x2 - x1;
  const len = Math.hypot(dx, y2 - y1);
  const droop = len * 0.13;
  const cy1 = y1 + droop * 0.6 - 1.8;
  const cy2 = y2 + droop * 0.4 - 1.8;
  return `M ${x1} ${y1 - 1.4} C ${x1 + dx * 0.42} ${cy1}, ${x2 - dx * 0.42} ${cy2}, ${x2} ${y2 - 1.4}`;
}

function buildPanelSpecs(
  refs: PanelRefs,
  ree: ReeEditorViewModel,
  badges: Badges,
): PanelCableSpec[] {
  const cableStates = getPodCableStates(ree, badges);
  const cableById = Object.fromEntries(cableStates.map((cable) => [cable.id, cable]));

  return [
    {
      id: "source",
      ref: refs.sourceRef,
      side: "right",
      color: cableById.source?.color || "#f59e0b",
      shadow: cableById.source?.shadow || "#92400e",
      connected: !!cableById.source?.connected,
    },
    {
      id: "runtime",
      ref: refs.runtimeRef,
      side: "right",
      color: cableById.runtime?.color || "#0891b2",
      shadow: cableById.runtime?.shadow || "#164e63",
      connected: !!cableById.runtime?.connected,
    },
    {
      id: "sbom",
      ref: refs.sbomRef,
      side: "right",
      color: cableById.sbom?.color || "#16a34a",
      shadow: cableById.sbom?.shadow || "#14532d",
      connected: !!cableById.sbom?.connected,
    },
    {
      id: "fields",
      ref: refs.metadataRef,
      side: "right",
      color: cableById.fields?.color || "#22c55e",
      shadow: cableById.fields?.shadow || "#166534",
      connected: !!cableById.fields?.connected,
    },
    {
      id: "hbom",
      ref: refs.hbomRef,
      side: "right",
      color: cableById.hbom?.color || "#0f766e",
      shadow: cableById.hbom?.shadow || "#134e4a",
      connected: !!cableById.hbom?.connected,
    },
    {
      id: "archive",
      ref: refs.archiveRef,
      side: "left",
      color: cableById.archive?.color || "#e4572e",
      shadow: cableById.archive?.shadow || "#7c2d12",
      connected: !!cableById.archive?.connected,
    },
    {
      id: "activation",
      ref: refs.activationRef,
      side: "left",
      color: cableById.activation?.color || "#7c3aed",
      shadow: cableById.activation?.shadow || "#3b0764",
      connected: !!cableById.activation?.connected,
    },
    {
      id: "swh",
      ref: refs.swhRef,
      side: "left",
      color: cableById.swh?.color || "#e4572e",
      shadow: cableById.swh?.shadow || "#7c2d12",
      connected: !!cableById.swh?.connected,
    },
    {
      id: "evaluate",
      ref: refs.evaluateRef,
      side: "left",
      color: cableById.evaluate?.color || "#7c3aed",
      shadow: cableById.evaluate?.shadow || "#3b0764",
      connected: !!cableById.evaluate?.connected,
    },
    {
      id: "seal",
      ref: refs.sealRef,
      side: "top",
      color: cableById.seal?.color || "#f59e0b",
      shadow: cableById.seal?.shadow || "#78350f",
      connected: !!cableById.seal?.connected,
    },
  ];
}

export function measureCableGeo(args: {
  container: HTMLElement;
  podSvg: SVGSVGElement;
  refs: PanelRefs;
  ree: ReeEditorViewModel;
  badges: Badges;
}): CableGeo | null {
  const { container, podSvg, refs, ree, badges } = args;
  const cRect = container.getBoundingClientRect();
  const SvgCx = 290;
  const SvgCy = 290;
  const SvgSr = 118;

  const sphereC = svgPtToContainer(podSvg, container, SvgCx, SvgCy);
  if (!sphereC) return null;
  const sphereEdge = svgPtToContainer(podSvg, container, SvgCx + SvgSr, SvgCy);
  if (!sphereEdge) return null;
  const sphereRadius = sphereEdge.x - sphereC.x;

  const panelRel = (el: HTMLElement | null) => {
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return {
      left: rect.left - cRect.left,
      right: rect.right - cRect.left,
      midY: (rect.top + rect.bottom) / 2 - cRect.top,
      midX: (rect.left + rect.right) / 2 - cRect.left,
      top: rect.top - cRect.top,
    };
  };

  const sphereIntercept = (panelX: number, panelY: number) => {
    const dx = panelX - sphereC.x;
    const dy = panelY - sphereC.y;
    const len = Math.hypot(dx, dy) || 1;
    return { x: sphereC.x + (dx / len) * sphereRadius, y: sphereC.y + (dy / len) * sphereRadius };
  };

  const panelSpecs = buildPanelSpecs(refs, ree, badges);
  const cables: Cable[] = [];
  panelSpecs.forEach((panelSpec) => {
    const panel = panelRel(panelSpec.ref.current);
    if (!panel) return;

    let px = panel.midX;
    let py = panel.midY;
    if (panelSpec.side === "left") px = panel.left;
    if (panelSpec.side === "right") px = panel.right;
    if (panelSpec.side === "top") py = panel.top;

    const pod = sphereIntercept(px, py);
    cables.push({
      id: panelSpec.id,
      x1: px,
      y1: py,
      x2: pod.x,
      y2: pod.y,
      color: panelSpec.color,
      shadow: panelSpec.shadow,
      connected: panelSpec.connected,
    });
  });

  const decoCables = DECO_ANCHORS.map((anc) => {
    const sa = (anc.angle * Math.PI) / 180;
    const startSvg = { x: SvgCx + SvgSr * Math.cos(sa), y: SvgCy + SvgSr * Math.sin(sa) };
    const endSvg = { x: SvgCx + anc.dist * Math.cos(sa), y: SvgCy + anc.dist * Math.sin(sa) };
    const start = svgPtToContainer(podSvg, container, startSvg.x, startSvg.y);
    const end = svgPtToContainer(podSvg, container, endSvg.x, endSvg.y);
    if (!start || !end) return null;
    return { id: anc.id, x1: start.x, y1: start.y, x2: end.x, y2: end.y };
  }).filter(
    (cable): cable is { id: string; x1: number; y1: number; x2: number; y2: number } =>
      cable !== null,
  );

  return { cables, decoCables, w: cRect.width, h: cRect.height };
}

export type { PanelRefs };
