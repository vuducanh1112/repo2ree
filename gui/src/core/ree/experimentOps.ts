import { createEmptyReeExperiment, type ReeExperiment, type ReeSpec } from "./ReeSpec";

export function addExperiment(spec: ReeSpec): ReeSpec {
  return {
    ...spec,
    experiments: [...(spec.experiments ?? []), createEmptyReeExperiment()],
  };
}

export function patchExperiment(
  spec: ReeSpec,
  index: number,
  patch: Partial<ReeExperiment>,
): ReeSpec {
  return {
    ...spec,
    experiments: (spec.experiments ?? []).map((e, i) => (i === index ? { ...e, ...patch } : e)),
  };
}

export function removeExperiment(spec: ReeSpec, index: number): ReeSpec {
  return {
    ...spec,
    experiments: (spec.experiments ?? []).filter((_, i) => i !== index),
  };
}
