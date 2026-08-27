// The three orthogonal reproducibility axes. Single source of truth for their
// labels and step names — shared by the Evaluate page and the pod widget. How an
// axis looks is keyed off `key` in the shell (see theme/tones.css).

import type { EvaluationState } from "./EvaluationState";

export type AxisKey = "dependency" | "environment" | "machine";

interface AxisMeta {
  key: AxisKey;
  label: string;
  short: string;
  steps: readonly string[];
}

export const DEPENDENCY_AXIS: AxisMeta = {
  key: "dependency",
  label: "Dependencies",
  short: "DEP",
  steps: ["None", "Declared", "Pinned", "Locked"],
};

export const ENVIRONMENT_AXIS: AxisMeta = {
  key: "environment",
  label: "Environment",
  short: "ENV",
  steps: ["None", "Container", "Declarative"],
};

export const MACHINE_AXIS: AxisMeta = {
  key: "machine",
  label: "Machine",
  short: "VM",
  steps: ["None", "Virtual machine"],
};

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
 * aggregate audit instead. */
export function bottleneckAxis(evaluation: EvaluationState): AxisStanding {
  return axisStandings(evaluation).reduce((weakest, standing) =>
    axisFraction(standing.axis, standing.level) < axisFraction(weakest.axis, weakest.level)
      ? standing
      : weakest,
  );
}
