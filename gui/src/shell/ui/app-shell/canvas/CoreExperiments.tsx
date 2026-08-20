import { PAGE } from "@core/app-shell/pages";
import type { ReeExperiment } from "@core/ree/ReeSpec";
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { stageTone } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import styles from "./CoreExperiments.module.css";
import type { CoreCableTarget } from "./useExperimentCables";

// The experiments live in the `core` zone of the master canvas, so the core
// column keeps that node's indigo — the satellite cables read as the same family.
const _EXP_COLOR = stageTone(PAGE.EXPERIMENTS);
const _EXP_SHADOW = stageTone(PAGE.EXPERIMENTS, "ink");
const ADD_KEY = "__add-experiment__";

function satelliteKey(index: number): string {
  return `exp-${String(index)}`;
}

// An experiment is "wired" once it has a run script — the minimum that makes
// its panel a runnable check. Drives whether its cable reads lit or dim. (Run /
// reproduce status will refine this later; for now it's the script's presence.)
function isExperimentWired(exp: ReeExperiment): boolean {
  return exp.runScript.trim() !== "";
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
    stageKey: PAGE.EXPERIMENTS,
  }));
  if (withAddSlot) {
    targets.push({ key: ADD_KEY, connected: false, stageKey: PAGE.EXPERIMENTS });
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
  onStartDrag: (key: string, event: React.PointerEvent) => void;
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
  const [_hovered, setHovered] = useState(false);
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
      className={styles.coreHit}
      style={cssVars({
        "--core-x": `${center.x}px`,
        "--core-y": `${center.y}px`,
        "--core-size": `${podDiameter}px`,
        "--core-label": label,
      })}
    >
      <span className={styles.coreLabel}>{Ic.layers(label)} Open catalog</span>
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
  onStartDrag: (key: string, event: React.PointerEvent) => void;
  wasNodeDragged: React.RefObject<boolean>;
}) {
  const name = experiment.name.trim();
  const command = experiment.runScript.trim();
  const wired = isExperimentWired(experiment);
  return (
    <button
      type="button"
      data-canvas-node
      aria-label={name || `Experiment ${String(index + 1).padStart(2, "0")}`}
      ref={setRef}
      onPointerDown={(event) => {
        if (!locked) onStartDrag(satelliteKey(index), event);
      }}
      onClick={() => {
        if (wasNodeDragged.current) return;
        onSelect();
      }}
      className={styles.satellite}
      data-wired={wired || undefined}
      style={cssVars({ "--sat-x": `${x}px`, "--sat-y": `${y}px`, "--sat-scale": scale })}
    >
      <div className={styles.satelliteHead}>
        <span className={styles.index}>{String(index + 1).padStart(2, "0")}</span>
        <span className={styles.name} data-untitled={name ? undefined : true}>
          {name || "untitled"}
        </span>
        <span aria-hidden className={styles.wiredDot} />
      </div>
      <div className={styles.command} data-unset={command ? undefined : true}>
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
      className={styles.addSlot}
      style={cssVars({ "--sat-x": `${x}px`, "--sat-y": `${y}px`, "--sat-scale": scale })}
    >
      {Ic.plus(15)} Add experiment
    </button>
  );
}
