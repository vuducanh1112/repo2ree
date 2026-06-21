import type { ReeExperiment } from "@core/ree/ReeSpec";
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import type { CoreCableTarget } from "./useExperimentCables";

// The experiments live in the `core` zone of the master canvas, so the core
// column keeps that node's indigo — the satellite cables read as the same family.
const EXP_COLOR = "#4f46e5";
const EXP_SHADOW = "#3730a3";
const ADD_KEY = "__add-experiment__";

function satelliteKey(index: number): string {
  return `exp-${String(index)}`;
}

// An experiment is "wired" once it has a command — the minimum that makes its
// panel a runnable check. Drives whether its cable reads lit or dim. (Run /
// reproduce status will refine this later; for now it's the command's presence.)
function isExperimentWired(exp: ReeExperiment): boolean {
  return exp.command.trim() !== "";
}

// The cable identities for the core column: one per experiment, plus a dim one
// for the add-ghost so a fresh slot reads as "not yet wired" rather than loose.
export function experimentCableTargets(
  experiments: ReeExperiment[],
  withAddSlot: boolean,
): CoreCableTarget[] {
  const targets: CoreCableTarget[] = experiments.map((exp, i) => ({
    key: satelliteKey(i),
    connected: isExperimentWired(exp),
    color: EXP_COLOR,
    shadow: EXP_SHADOW,
  }));
  if (withAddSlot) {
    targets.push({ key: ADD_KEY, connected: false, color: EXP_COLOR, shadow: EXP_SHADOW });
  }
  return targets;
}

interface CoreExperimentsProps {
  experiments: ReeExperiment[];
  locked: boolean;
  /** World position of the core column's pod centre. */
  center: { x: number; y: number };
  /** Diameter of the core pod in world units — sizes the clickable core hit area. */
  podDiameter: number;
  /** Per-satellite ring positions (origin-centred; this adds `center`). */
  positions: { x: number; y: number }[];
  /** Card scale, to sit in proportion with the miniaturised core column. */
  scale: number;
  satEls: React.MutableRefObject<Record<string, HTMLElement | null>>;
  nodeOffsets: Record<string, { x: number; y: number }>;
  onStartDrag: (key: string, sx: number, sy: number) => void;
  wasNodeDragged: React.RefObject<boolean>;
  /** Reports hover over the core pod so the parent can make the pod shine. */
  onCoreHoverChange: (hovered: boolean) => void;
  /** Core pod → the experiment catalog overview. */
  onOpenOverview: () => void;
  /** A satellite → that one experiment's editor. */
  onOpenExperiment: (index: number) => void;
  onAddExperiment: () => void;
}

// Renders the core column's experiment satellites + add-ghost into the world
// layer, plus a transparent hit area over the core pod so the pod itself opens
// the Experiments page. Cables for these are measured/drawn by the parent.
export function CoreExperiments({
  experiments,
  locked,
  center,
  podDiameter,
  positions,
  scale,
  satEls,
  nodeOffsets,
  onStartDrag,
  wasNodeDragged,
  onCoreHoverChange,
  onOpenOverview,
  onOpenExperiment,
  onAddExperiment,
}: CoreExperimentsProps) {
  const withAddSlot = !locked;
  return (
    <>
      {/* the core pod itself is the overview affordance */}
      <CoreOverviewButton
        center={center}
        podDiameter={podDiameter}
        wasNodeDragged={wasNodeDragged}
        onHoverChange={onCoreHoverChange}
        onOpenOverview={onOpenOverview}
      />

      {experiments.map((exp, index) => {
        const pos = positions[index];
        if (!pos) return null;
        const off = nodeOffsets[satelliteKey(index)] ?? { x: 0, y: 0 };
        return (
          <ExperimentSatellite
            key={satelliteKey(index)}
            index={index}
            experiment={exp}
            x={center.x + pos.x + off.x}
            y={center.y + pos.y + off.y}
            scale={scale}
            locked={locked}
            setRef={(el) => {
              satEls.current[satelliteKey(index)] = el;
            }}
            onSelect={() => onOpenExperiment(index)}
            onStartDrag={onStartDrag}
            wasNodeDragged={wasNodeDragged}
          />
        );
      })}

      {withAddSlot && positions[experiments.length] && (
        <AddSatellite
          x={center.x + positions[experiments.length].x}
          y={center.y + positions[experiments.length].y}
          scale={scale}
          setRef={(el) => {
            satEls.current[ADD_KEY] = el;
          }}
          onAdd={onAddExperiment}
        />
      )}
    </>
  );
}

// The core pod doubles as the "open the catalog" affordance. A pod is just a
// graphic, so hovering it makes the pod itself shine (driven in CanvasHub) and
// pops a label — this is just the transparent hit area that reports the hover.
function CoreOverviewButton({
  center,
  podDiameter,
  wasNodeDragged,
  onHoverChange,
  onOpenOverview,
}: {
  center: { x: number; y: number };
  podDiameter: number;
  wasNodeDragged: React.RefObject<boolean>;
  onHoverChange: (hovered: boolean) => void;
  onOpenOverview: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const setHover = (next: boolean) => {
    setHovered(next);
    onHoverChange(next);
  };
  // World-unit type sizing: scaled down with the core column, so it's generous
  // here to stay legible.
  const label = Math.round(podDiameter * 0.11);
  return (
    <button
      type="button"
      data-canvas-node
      aria-label="Open experiments"
      title="Open the experiment catalog"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={() => setHover(false)}
      onClick={() => {
        if (wasNodeDragged.current) return;
        onOpenOverview();
      }}
      style={{
        position: "absolute",
        left: center.x,
        top: center.y,
        width: podDiameter,
        height: podDiameter,
        transform: "translate(-50%,-50%)",
        borderRadius: "50%",
        border: "none",
        background: "transparent",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          position: "absolute",
          left: "50%",
          top: "100%",
          transform: "translate(-50%, 14px)",
          display: "inline-flex",
          alignItems: "center",
          gap: label * 0.4,
          whiteSpace: "nowrap",
          padding: `${label * 0.45}px ${label * 0.9}px`,
          borderRadius: 999,
          background: EXP_COLOR,
          color: "#fff",
          fontFamily: F.sans,
          fontWeight: 700,
          fontSize: label,
          boxShadow: `0 ${label * 0.3}px ${label}px ${EXP_SHADOW}55`,
          opacity: hovered ? 1 : 0,
          transition: "opacity 0.15s",
          pointerEvents: "none",
        }}
      >
        {Ic.layers(label)} Open catalog
      </span>
    </button>
  );
}

function ExperimentSatellite({
  index,
  experiment,
  x,
  y,
  scale,
  locked,
  setRef,
  onSelect,
  onStartDrag,
  wasNodeDragged,
}: {
  index: number;
  experiment: ReeExperiment;
  x: number;
  y: number;
  scale: number;
  locked: boolean;
  setRef: (el: HTMLButtonElement | null) => void;
  onSelect: () => void;
  onStartDrag: (key: string, sx: number, sy: number) => void;
  wasNodeDragged: React.RefObject<boolean>;
}) {
  const name = experiment.name.trim();
  const command = experiment.command.trim();
  const wired = isExperimentWired(experiment);
  return (
    <button
      type="button"
      data-canvas-node
      aria-label={name || `Experiment ${String(index + 1).padStart(2, "0")}`}
      ref={setRef}
      onMouseDown={(e) => {
        if (!locked) onStartDrag(satelliteKey(index), e.clientX, e.clientY);
      }}
      onClick={() => {
        if (wasNodeDragged.current) return;
        onSelect();
      }}
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%,-50%) scale(${scale})`,
        width: 188,
        textAlign: "left",
        background: C.surface,
        border: `1px solid ${wired ? "#c7d2fe" : C.border}`,
        borderRadius: 13,
        padding: "11px 13px",
        cursor: "pointer",
        boxShadow: wired ? "0 6px 20px rgba(79,70,229,0.14)" : "0 4px 16px rgba(13,17,23,0.07)",
        transition: "box-shadow 0.15s, border-color 0.15s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span
          style={{
            fontFamily: F.mono,
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: "0.08em",
            color: EXP_COLOR,
            border: `1px solid ${EXP_COLOR}44`,
            background: "#eef2ff",
            borderRadius: 6,
            padding: "2px 7px",
          }}
        >
          {String(index + 1).padStart(2, "0")}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 13,
            fontWeight: 650,
            color: name ? C.text : C.textMuted,
            fontStyle: name ? "normal" : "italic",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {name || "untitled"}
        </span>
        <span
          style={{
            width: 9,
            height: 9,
            borderRadius: "50%",
            flexShrink: 0,
            background: wired ? C.done : C.borderMid,
            boxShadow: wired ? `0 0 0 3px ${C.done}22` : "none",
          }}
        />
      </div>
      <div
        style={{
          fontFamily: F.mono,
          fontSize: 11,
          color: command ? C.textMid : C.textMuted,
          background: C.surfaceAlt,
          border: `1px solid ${C.border}`,
          borderRadius: 7,
          padding: "6px 9px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          opacity: command ? 1 : 0.7,
        }}
      >
        {command || "no command set"}
      </div>
    </button>
  );
}

// The trailing ring slot: clicking it spawns a new experiment satellite.
function AddSatellite({
  x,
  y,
  scale,
  setRef,
  onAdd,
}: {
  x: number;
  y: number;
  scale: number;
  setRef: (el: HTMLButtonElement | null) => void;
  onAdd: () => void;
}) {
  return (
    <button
      type="button"
      data-canvas-node
      aria-label="Add experiment"
      title="Add experiment"
      ref={setRef}
      onClick={onAdd}
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%,-50%) scale(${scale})`,
        width: 188,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        background: "rgba(238,242,255,0.6)",
        border: `1.5px dashed ${EXP_COLOR}77`,
        borderRadius: 13,
        padding: "16px 13px",
        cursor: "pointer",
        color: EXP_COLOR,
        fontSize: 13,
        fontWeight: 650,
        fontFamily: F.sans,
      }}
    >
      {Ic.plus(15)} Add experiment
    </button>
  );
}
