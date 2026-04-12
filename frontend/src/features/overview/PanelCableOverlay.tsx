import React, { useRef } from "react";
import { LEVELS } from "../../constants/levels";
import type { Badges, Ree } from "../../types";
import { getPodCableStates } from "./podCableState";

interface Cable {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
  shadow: string;
  connected: boolean;
}

interface CableGeo {
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

interface PanelCableOverlayProps {
  containerRef: React.RefObject<HTMLDivElement>;
  sourceRef: React.RefObject<HTMLDivElement>;
  runtimeRef: React.RefObject<HTMLDivElement>;
  metadataRef: React.RefObject<HTMLDivElement>;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  sbomRef: React.RefObject<HTMLDivElement>;
  sealRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
  podSvgRef: React.RefObject<SVGSVGElement>;
  level: number;
  badges: Badges;
  ree: Ree;
}

type PanelCableSide = "left" | "right" | "top";

interface PanelCableSpec {
  id: string;
  ref: React.RefObject<HTMLDivElement>;
  side: PanelCableSide;
  color: string;
  shadow: string;
  connected: boolean;
}

interface Point {
  x: number;
  y: number;
}

interface PanelRect {
  left: number;
  right: number;
  midY: number;
  midX: number;
  top: number;
}

interface PanelRefs {
  sourceRef: React.RefObject<HTMLDivElement>;
  runtimeRef: React.RefObject<HTMLDivElement>;
  metadataRef: React.RefObject<HTMLDivElement>;
  sbomRef: React.RefObject<HTMLDivElement>;
  archiveRef: React.RefObject<HTMLDivElement>;
  activationRef: React.RefObject<HTMLDivElement>;
  swhRef: React.RefObject<HTMLDivElement>;
  evaluateRef: React.RefObject<HTMLDivElement>;
  sealRef: React.RefObject<HTMLDivElement>;
}

interface CableStateLite {
  color?: string;
  shadow?: string;
  connected?: boolean;
}

interface PanelSpecConfig {
  id: string;
  refKey: keyof PanelRefs;
  side: PanelCableSide;
  defaultColor: string;
  defaultShadow: string;
}

type SvgToContainer = (
  svg: SVGSVGElement,
  container: HTMLElement,
  px: number,
  py: number,
) => { x: number; y: number } | null;

const PANEL_SPEC_CONFIGS: PanelSpecConfig[] = [
  {
    id: "source",
    refKey: "sourceRef",
    side: "right",
    defaultColor: "#f59e0b",
    defaultShadow: "#92400e",
  },
  {
    id: "runtime",
    refKey: "runtimeRef",
    side: "right",
    defaultColor: "#0891b2",
    defaultShadow: "#164e63",
  },
  {
    id: "sbom",
    refKey: "sbomRef",
    side: "right",
    defaultColor: "#16a34a",
    defaultShadow: "#14532d",
  },
  {
    id: "fields",
    refKey: "metadataRef",
    side: "right",
    defaultColor: "#22c55e",
    defaultShadow: "#166534",
  },
  {
    id: "archive",
    refKey: "archiveRef",
    side: "left",
    defaultColor: "#e4572e",
    defaultShadow: "#7c2d12",
  },
  {
    id: "activation",
    refKey: "activationRef",
    side: "left",
    defaultColor: "#7c3aed",
    defaultShadow: "#3b0764",
  },
  {
    id: "swh",
    refKey: "swhRef",
    side: "left",
    defaultColor: "#e4572e",
    defaultShadow: "#7c2d12",
  },
  {
    id: "evaluate",
    refKey: "evaluateRef",
    side: "left",
    defaultColor: "#7c3aed",
    defaultShadow: "#3b0764",
  },
  {
    id: "seal",
    refKey: "sealRef",
    side: "top",
    defaultColor: "#f59e0b",
    defaultShadow: "#78350f",
  },
];

function getPanelRect(el: HTMLElement | null, containerRect: DOMRect): PanelRect | null {
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return {
    left: rect.left - containerRect.left,
    right: rect.right - containerRect.left,
    midY: (rect.top + rect.bottom) / 2 - containerRect.top,
    midX: (rect.left + rect.right) / 2 - containerRect.left,
    top: rect.top - containerRect.top,
  };
}

function sphereIntercept(
  panelX: number,
  panelY: number,
  sphereCenter: Point,
  sphereRadius: number,
): Point {
  const dx = panelX - sphereCenter.x;
  const dy = panelY - sphereCenter.y;
  const len = Math.hypot(dx, dy) || 1;
  return {
    x: sphereCenter.x + (dx / len) * sphereRadius,
    y: sphereCenter.y + (dy / len) * sphereRadius,
  };
}

function buildPanelCables(
  panelSpecs: PanelCableSpec[],
  containerRect: DOMRect,
  sphereCenter: Point,
  sphereRadius: number,
): Cable[] {
  const cables: Cable[] = [];
  for (const panelSpec of panelSpecs) {
    const panel = getPanelRect(panelSpec.ref.current, containerRect);
    if (!panel) continue;

    let px = panel.midX;
    let py = panel.midY;
    if (panelSpec.side === "left") px = panel.left;
    if (panelSpec.side === "right") px = panel.right;
    if (panelSpec.side === "top") py = panel.top;

    const pod = sphereIntercept(px, py, sphereCenter, sphereRadius);
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
  }
  return cables;
}

function buildPanelSpecs(
  cableById: Record<string, CableStateLite | undefined>,
  refs: PanelRefs,
): PanelCableSpec[] {
  return PANEL_SPEC_CONFIGS.map((config) => {
    const cable = cableById[config.id];
    return {
      id: config.id,
      ref: refs[config.refKey],
      side: config.side,
      color: cable?.color || config.defaultColor,
      shadow: cable?.shadow || config.defaultShadow,
      connected: !!cable?.connected,
    };
  });
}

function buildDecoCables(
  svgPtToContainer: SvgToContainer,
  podSvg: SVGSVGElement,
  container: HTMLElement,
  svgCenter: Point,
  sphereRadius: number,
) {
  return DECO_ANCHORS.map((anc) => {
    const sa = (anc.angle * Math.PI) / 180;
    const startSvg = {
      x: svgCenter.x + sphereRadius * Math.cos(sa),
      y: svgCenter.y + sphereRadius * Math.sin(sa),
    };
    const endSvg = {
      x: svgCenter.x + anc.dist * Math.cos(sa),
      y: svgCenter.y + anc.dist * Math.sin(sa),
    };
    const start = svgPtToContainer(podSvg, container, startSvg.x, startSvg.y);
    const end = svgPtToContainer(podSvg, container, endSvg.x, endSvg.y);
    if (!start || !end) return null;
    return { id: anc.id, x1: start.x, y1: start.y, x2: end.x, y2: end.y };
  }).filter(
    (
      cable,
    ): cable is {
      id: string;
      x1: number;
      y1: number;
      x2: number;
      y2: number;
    } => cable !== null,
  );
}

export function PanelCableOverlay({
  containerRef,
  sourceRef,
  runtimeRef,
  metadataRef,
  swhRef,
  evaluateRef,
  sbomRef,
  sealRef,
  archiveRef,
  activationRef,
  podSvgRef,
  level,
  badges,
  ree,
}: PanelCableOverlayProps) {
  const levelMeta = LEVELS[Math.min(level, 7)];
  const [geo, setGeo] = React.useState<CableGeo | null>(null);
  const rafRef = useRef<number | null>(null);

  const svgPtToContainer = React.useCallback(
    (
      svg: SVGSVGElement,
      container: HTMLElement,
      px: number,
      py: number,
    ): { x: number; y: number } | null => {
      const ctm = svg.getScreenCTM();
      if (!ctm) return null;
      const cRect = container.getBoundingClientRect();
      return {
        x: ctm.a * px + ctm.c * py + ctm.e - cRect.left,
        y: ctm.b * px + ctm.d * py + ctm.f - cRect.top,
      };
    },
    [],
  );

  const measure = React.useCallback(() => {
    const container = containerRef.current;
    const podSvg = podSvgRef.current;
    if (!container || !podSvg) return;

    const cRect = container.getBoundingClientRect();
    const SvgCx = 290,
      SvgCy = 290,
      SvgSr = 118;

    const sphereC = svgPtToContainer(podSvg, container, SvgCx, SvgCy);
    if (!sphereC) return;

    const sphereEdge = svgPtToContainer(podSvg, container, SvgCx + SvgSr, SvgCy);
    if (!sphereEdge) return;
    const sphereR = sphereEdge.x - sphereC.x;

    const sphereCenter = sphereC;
    const sphereRadius = sphereR;

    const cableStates = getPodCableStates(ree, badges);
    const cableById = Object.fromEntries(cableStates.map((cable) => [cable.id, cable])) as Record<
      string,
      CableStateLite | undefined
    >;
    const panelSpecs = buildPanelSpecs(cableById, {
      sourceRef,
      runtimeRef,
      metadataRef,
      sbomRef,
      archiveRef,
      activationRef,
      swhRef,
      evaluateRef,
      sealRef,
    });

    const cables = buildPanelCables(panelSpecs, cRect, sphereCenter, sphereRadius);

    const decoCables = buildDecoCables(
      svgPtToContainer,
      podSvg,
      container,
      { x: SvgCx, y: SvgCy },
      SvgSr,
    );

    const w = cRect.width,
      h = cRect.height;
    setGeo({ cables, decoCables, w, h });
  }, [
    activationRef,
    archiveRef,
    badges,
    containerRef,
    evaluateRef,
    metadataRef,
    podSvgRef,
    ree,
    runtimeRef,
    sbomRef,
    sealRef,
    sourceRef,
    swhRef,
    svgPtToContainer,
  ]);

  React.useEffect(() => {
    rafRef.current = requestAnimationFrame(measure);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [measure]);

  React.useEffect(() => {
    const panelRefs = [
      sourceRef,
      runtimeRef,
      metadataRef,
      swhRef,
      evaluateRef,
      sbomRef,
      sealRef,
      archiveRef,
      activationRef,
    ];
    const targets = [containerRef, ...panelRefs] as React.RefObject<Element>[];

    const ro = new ResizeObserver(() => {
      rafRef.current = requestAnimationFrame(measure);
    });

    for (const targetRef of targets) {
      if (targetRef.current) ro.observe(targetRef.current);
    }
    return () => ro.disconnect();
  });

  if (!geo) return null;
  const { cables, decoCables, w, h } = geo;

  function cablePath(x1: number, y1: number, x2: number, y2: number): string {
    const dx = x2 - x1;
    const len = Math.hypot(dx, y2 - y1);
    const droop = len * 0.13;
    const cx1 = x1 + dx * 0.42,
      cy1 = y1 + droop * 0.6;
    const cx2 = x2 - dx * 0.42,
      cy2 = y2 + droop * 0.4;
    return `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
  }

  function cableHl(x1: number, y1: number, x2: number, y2: number): string {
    const dx = x2 - x1;
    const len = Math.hypot(dx, y2 - y1);
    const droop = len * 0.13;
    const cy1 = y1 + droop * 0.6 - 1.8;
    const cy2 = y2 + droop * 0.4 - 1.8;
    return `M ${x1} ${y1 - 1.4} C ${x1 + dx * 0.42} ${cy1}, ${x2 - dx * 0.42} ${cy2}, ${x2} ${y2 - 1.4}`;
  }

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        overflow: "visible",
        zIndex: 0,
      }}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
    >
      <title>Panel connections</title>
      <defs>
        {(decoCables || []).map((dc) => (
          <linearGradient
            key={dc.id}
            id={`oDecoFade_${dc.id}`}
            gradientUnits="userSpaceOnUse"
            x1={dc.x1}
            y1={dc.y1}
            x2={dc.x2}
            y2={dc.y2}
          >
            <stop offset="0%" stopColor="white" stopOpacity="1" />
            <stop offset="60%" stopColor="white" stopOpacity="1" />
            <stop offset="85%" stopColor="white" stopOpacity="0.35" />
            <stop offset="100%" stopColor="white" stopOpacity="0" />
          </linearGradient>
        ))}
        {(decoCables || []).map((dc) => (
          <mask key={dc.id} id={`oDecoMask_${dc.id}`}>
            <rect x="0" y="0" width={w} height={h} fill={`url(#oDecoFade_${dc.id})`} />
          </mask>
        ))}
      </defs>
      {(decoCables || []).map((dc) => {
        const d = cablePath(dc.x1, dc.y1, dc.x2, dc.y2);
        const dHl = cableHl(dc.x1, dc.y1, dc.x2, dc.y2);
        return (
          <g key={dc.id} opacity="0.32" mask={`url(#oDecoMask_${dc.id})`}>
            <path
              d={d}
              fill="none"
              stroke="#334155"
              strokeWidth="12"
              opacity="0.12"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke="#94a3b8"
              strokeWidth="8"
              opacity="0.5"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="4"
              opacity="0.75"
              strokeLinecap="round"
            />
            <path
              d={dHl}
              fill="none"
              stroke="#ffffff"
              strokeWidth="1.5"
              opacity="0.55"
              strokeLinecap="round"
            />
          </g>
        );
      })}
      {cables.map((c) => {
        const color = c.connected ? c.color : "#94a3b8";
        const shadow = c.connected ? c.shadow : "#334155";
        const inner = c.connected ? levelMeta.bg : "#e2e8f0";
        const d = cablePath(c.x1, c.y1, c.x2, c.y2);
        const dHl = cableHl(c.x1, c.y1, c.x2, c.y2);
        return (
          <g key={c.id} opacity={c.connected ? 1 : 0.38}>
            <path
              d={d}
              fill="none"
              stroke={shadow}
              strokeWidth="14"
              opacity="0.16"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke={color}
              strokeWidth="9"
              opacity="0.55"
              strokeLinecap="round"
            />
            <path
              d={d}
              fill="none"
              stroke={inner}
              strokeWidth="5"
              opacity="0.80"
              strokeLinecap="round"
            />
            <path
              d={dHl}
              fill="none"
              stroke="#ffffff"
              strokeWidth="1.8"
              opacity="0.60"
              strokeLinecap="round"
            />
            <circle cx={c.x1} cy={c.y1} r="5.5" fill={color} stroke={shadow} strokeWidth="1.3" />
            <circle cx={c.x1} cy={c.y1} r="2.4" fill="#fff" opacity="0.85" />
            <circle cx={c.x2} cy={c.y2} r="5.5" fill={color} stroke={shadow} strokeWidth="1.3" />
            <circle cx={c.x2} cy={c.y2} r="2.4" fill="#fff" opacity="0.85" />
          </g>
        );
      })}
    </svg>
  );
}
