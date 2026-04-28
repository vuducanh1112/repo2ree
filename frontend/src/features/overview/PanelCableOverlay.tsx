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
  hbomRef: React.RefObject<HTMLDivElement>;
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

export function PanelCableOverlay({
  containerRef,
  sourceRef,
  runtimeRef,
  metadataRef,
  hbomRef,
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

    function panelRel(
      el: HTMLElement | null,
    ): { left: number; right: number; midY: number; midX: number; top: number } | null {
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return {
        left: rect.left - cRect.left,
        right: rect.right - cRect.left,
        midY: (rect.top + rect.bottom) / 2 - cRect.top,
        midX: (rect.left + rect.right) / 2 - cRect.left,
        top: rect.top - cRect.top,
      };
    }

    const sphereCenter = sphereC;
    const sphereRadius = sphereR;

    function sphereIntercept(panelX: number, panelY: number): { x: number; y: number } {
      const dx = panelX - sphereCenter.x,
        dy = panelY - sphereCenter.y;
      const len = Math.hypot(dx, dy) || 1;
      return {
        x: sphereCenter.x + (dx / len) * sphereRadius,
        y: sphereCenter.y + (dy / len) * sphereRadius,
      };
    }

    const cableStates = getPodCableStates(ree, badges);
    const cableById = Object.fromEntries(cableStates.map((cable) => [cable.id, cable]));

    const panelSpecs: PanelCableSpec[] = [
      {
        id: "source",
        ref: sourceRef,
        side: "right",
        color: cableById.source?.color || "#f59e0b",
        shadow: cableById.source?.shadow || "#92400e",
        connected: !!cableById.source?.connected,
      },
      {
        id: "runtime",
        ref: runtimeRef,
        side: "right",
        color: cableById.runtime?.color || "#0891b2",
        shadow: cableById.runtime?.shadow || "#164e63",
        connected: !!cableById.runtime?.connected,
      },
      {
        id: "sbom",
        ref: sbomRef,
        side: "right",
        color: cableById.sbom?.color || "#16a34a",
        shadow: cableById.sbom?.shadow || "#14532d",
        connected: !!cableById.sbom?.connected,
      },
      {
        id: "fields",
        ref: metadataRef,
        side: "right",
        color: cableById.fields?.color || "#22c55e",
        shadow: cableById.fields?.shadow || "#166534",
        connected: !!cableById.fields?.connected,
      },
      {
        id: "hbom",
        ref: hbomRef,
        side: "right",
        color: cableById.hbom?.color || "#0f766e",
        shadow: cableById.hbom?.shadow || "#134e4a",
        connected: !!cableById.hbom?.connected,
      },
      {
        id: "archive",
        ref: archiveRef,
        side: "left",
        color: cableById.archive?.color || "#e4572e",
        shadow: cableById.archive?.shadow || "#7c2d12",
        connected: !!cableById.archive?.connected,
      },
      {
        id: "activation",
        ref: activationRef,
        side: "left",
        color: cableById.activation?.color || "#7c3aed",
        shadow: cableById.activation?.shadow || "#3b0764",
        connected: !!cableById.activation?.connected,
      },
      {
        id: "swh",
        ref: swhRef,
        side: "left",
        color: cableById.swh?.color || "#e4572e",
        shadow: cableById.swh?.shadow || "#7c2d12",
        connected: !!cableById.swh?.connected,
      },
      {
        id: "evaluate",
        ref: evaluateRef,
        side: "left",
        color: cableById.evaluate?.color || "#7c3aed",
        shadow: cableById.evaluate?.shadow || "#3b0764",
        connected: !!cableById.evaluate?.connected,
      },
      {
        id: "seal",
        ref: sealRef,
        side: "top",
        color: cableById.seal?.color || "#f59e0b",
        shadow: cableById.seal?.shadow || "#78350f",
        connected: !!cableById.seal?.connected,
      },
    ];

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
    hbomRef,
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

    targets.forEach((targetRef) => {
      if (targetRef.current) ro.observe(targetRef.current);
    });
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
