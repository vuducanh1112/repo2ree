import type { AppShellPage } from "@core/app-shell/pages";
import { type CableGeo, cableHl, cablePath } from "@core/canvas/cableGeometry";
import { stageTone } from "../../theme/appearance";
import styles from "./CableOverlay.module.css";

interface CableOverlaySvgProps {
  geo: CableGeo;
  levelMeta: { bg: string };
  /** Panels whose step is running; their cable carries visible traffic. */
  runningKeys: ReadonlySet<AppShellPage>;
}

interface CableStrandProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  outerColor: string;
  outerWidth: number;
  outerOpacity: number;
  midColor: string;
  midWidth: number;
  midOpacity: number;
  innerColor: string;
  innerWidth: number;
  innerOpacity: number;
  knobFill: string;
  knobStroke: string;
  /** Draws the travelling charge along the strand, panel end to pod. */
  energized: boolean;
}

function CableStrand({
  x1,
  y1,
  x2,
  y2,
  outerColor,
  outerWidth,
  outerOpacity,
  midColor,
  midWidth,
  midOpacity,
  innerColor,
  innerWidth,
  innerOpacity,
  knobFill,
  knobStroke,
  energized,
}: CableStrandProps) {
  const d = cablePath(x1, y1, x2, y2);
  const dHl = cableHl(x1, y1, x2, y2);
  return (
    <>
      <path
        d={d}
        fill="none"
        stroke={outerColor}
        strokeWidth={outerWidth}
        opacity={outerOpacity}
        strokeLinecap="round"
      />
      <path
        d={d}
        fill="none"
        stroke={midColor}
        strokeWidth={midWidth}
        opacity={midOpacity}
        strokeLinecap="round"
      />
      <path
        d={d}
        fill="none"
        stroke={innerColor}
        strokeWidth={innerWidth}
        opacity={innerOpacity}
        strokeLinecap="round"
      />
      {energized && (
        <path
          className={styles.charge}
          d={d}
          fill="none"
          stroke={midColor}
          strokeWidth={innerWidth}
          strokeLinecap="round"
          pathLength={100}
        />
      )}
      <path
        d={dHl}
        fill="none"
        stroke="var(--cable-gloss)"
        strokeWidth="1.8"
        opacity="0.60"
        strokeLinecap="round"
      />
      <circle cx={x1} cy={y1} r="5.5" fill={knobFill} stroke={knobStroke} strokeWidth="1.3" />
      <circle cx={x1} cy={y1} r="2.4" fill="var(--cable-gloss)" opacity="0.85" />
      <circle cx={x2} cy={y2} r="5.5" fill={knobFill} stroke={knobStroke} strokeWidth="1.3" />
      <circle cx={x2} cy={y2} r="2.4" fill="var(--cable-gloss)" opacity="0.85" />
    </>
  );
}

export function CableOverlaySvg({ geo, levelMeta, runningKeys }: CableOverlaySvgProps) {
  const { cables, w, h } = geo;

  return (
    <svg className={styles.overlay} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <title>Panel connections</title>
      {cables.map((c) => {
        const color = c.connected ? stageTone(c.stageKey) : "var(--cable-dim)";
        const shadow = c.connected ? stageTone(c.stageKey, "ink") : "var(--cable-dim-ink)";
        const inner = c.connected ? levelMeta.bg : "var(--cable-dim-core)";
        const energized = runningKeys.has(c.stageKey);
        return (
          <g
            key={c.id}
            className={styles.cable}
            data-connected={c.connected || undefined}
            data-energized={energized || undefined}
          >
            <CableStrand
              x1={c.x1}
              y1={c.y1}
              x2={c.x2}
              y2={c.y2}
              outerColor={shadow}
              outerWidth={14}
              outerOpacity={0.16}
              midColor={color}
              midWidth={9}
              midOpacity={0.55}
              innerColor={inner}
              innerWidth={5}
              innerOpacity={0.8}
              knobFill={color}
              knobStroke={shadow}
              energized={energized}
            />
          </g>
        );
      })}
    </svg>
  );
}
