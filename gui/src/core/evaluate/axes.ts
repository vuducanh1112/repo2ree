// The three orthogonal reproducibility axes. Single source of truth for their
// labels, step names and colors — shared by the Evaluate page and the pod widget.

import type { EvaluationState } from "./EvaluationState";

export type AxisKey = "dependency" | "environment" | "machine";

interface AxisMeta {
  key: AxisKey;
  label: string;
  short: string;
  steps: readonly string[];
  color: string;
  bg: string;
  ink: string;
}

export const DEPENDENCY_AXIS: AxisMeta = {
  key: "dependency",
  label: "Dependencies",
  short: "DEP",
  steps: ["None", "Declared", "Pinned", "Locked"],
  color: "#3b82f6",
  bg: "#eff6ff",
  ink: "#1d4ed8",
};

export const ENVIRONMENT_AXIS: AxisMeta = {
  key: "environment",
  label: "Environment",
  short: "ENV",
  steps: ["None", "Container", "Declarative"],
  color: "#06b6d4",
  bg: "#ecfeff",
  ink: "#0e7490",
};

export const MACHINE_AXIS: AxisMeta = {
  key: "machine",
  label: "Machine",
  short: "VM",
  steps: ["None", "Virtual machine"],
  color: "#6366f1",
  bg: "#eef2ff",
  ink: "#3730a3",
};

export const AXES: readonly AxisMeta[] = [DEPENDENCY_AXIS, ENVIRONMENT_AXIS, MACHINE_AXIS];

function axisMaxLevel(axis: AxisMeta): number {
  return axis.steps.length - 1;
}

function clampAxisLevel(axis: AxisMeta, level: number): number {
  return Math.max(0, Math.min(Math.trunc(level), axisMaxLevel(axis)));
}

export function axisStepLabel(axis: AxisMeta, level: number): string {
  return axis.steps[clampAxisLevel(axis, level)];
}

/** 0..1 progress of a level along its axis (0-step axes count any level>0 as full). */
export function axisFraction(axis: AxisMeta, level: number): number {
  const max = axisMaxLevel(axis);
  if (max <= 0) return level > 0 ? 1 : 0;
  return clampAxisLevel(axis, level) / max;
}

interface AxisStanding {
  axis: AxisMeta;
  level: number;
}

export function axisStandings(evaluation: EvaluationState): AxisStanding[] {
  return [
    { axis: DEPENDENCY_AXIS, level: evaluation.dependencyLevel ?? 0 },
    { axis: ENVIRONMENT_AXIS, level: evaluation.environmentLevel ?? 0 },
    { axis: MACHINE_AXIS, level: evaluation.machineLevel ?? 0 },
  ];
}

/** The least-complete axis of the *source repo* analysis — used only by the
 * pod's axis visualization. REE-level chrome (cables, seal card) tints from
 * the scorecard standing instead (see @core/scorecard). */
export function bottleneckAxis(evaluation: EvaluationState): AxisStanding {
  return axisStandings(evaluation).reduce((weakest, standing) =>
    axisFraction(standing.axis, standing.level) < axisFraction(weakest.axis, weakest.level)
      ? standing
      : weakest,
  );
}
