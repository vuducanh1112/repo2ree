import type {
  ReeStepKey,
  ReeStepParams,
  ReeStepParamsByKey,
  ReeStepRunParams,
} from "./stepRunParams";
import type { ReeStepDefinition } from "./stepTypes";

type ReeStep = ReeStepDefinition & { key: ReeStepKey };

export const REE_STEPS: ReeStep[] = [
  {
    key: "evaluate_reproducibility",
    label: "Reproducibility Readiness",
    iconKey: "star",
    outcomeLabel: "Evaluated",
    desc: "Analyze the source repository as anyone would clone it: dependency declaration, environment capture, and the concrete threats to reproducing it.",
    params: [
      {
        key: "strict",
        label: "Strict mode",
        type: "bool",
        default: false,
        hint: "Fail if any optional fields are missing",
      },
    ],
  },
  {
    key: "build_experiment_environment",
    label: "Build Experiment Environment",
    iconKey: "cpu",
    outcomeLabel: "Built",
    desc: "Run the reserved build script and refresh the workspace after a successful build.",
    params: [],
  },
  {
    key: "observe_hardware",
    label: "Profile Machine",
    iconKey: "chip",
    outcomeLabel: "HBOM profiled",
    desc: "Inspect the current machine and prefill the HBOM with detected CPU, GPU, memory, storage, and network details.",
    params: [],
  },
  {
    key: "generate_sbom",
    label: "Generate SBOM",
    iconKey: "package",
    outcomeLabel: "SBOM ready",
    desc: "Generate a complete list of all software in your environment. This runs syft on the built experiment environment tarball (squashed scope) and outputs a CycloneDX JSON SBOM, which the cross-check joins against the scanned dependency inventory.",
    params: [],
  },
  {
    key: "activate_experiment_environment",
    label: "Test Activation",
    iconKey: "shield",
    outcomeLabel: "Activation passed",
    desc: "Check that the packaged environment actually starts and activates. This enters the experiment environment through its configured entry and runs the activation command, the same way experiments enter the experiment environment.",
    params: [],
  },
];

const DEFAULT_REE_STEP_PARAMS: ReeStepParams = {
  evaluate_reproducibility: { strict: false },
  build_experiment_environment: {},
  observe_hardware: {},
  generate_sbom: {},
  activate_experiment_environment: {},
};

export function defaultParamsForReeStep<K extends ReeStepKey>(key: K): ReeStepParamsByKey[K] {
  return DEFAULT_REE_STEP_PARAMS[key];
}

export function initialReeStepParams(): ReeStepParams {
  return {
    evaluate_reproducibility: { ...DEFAULT_REE_STEP_PARAMS.evaluate_reproducibility },
    build_experiment_environment: { ...DEFAULT_REE_STEP_PARAMS.build_experiment_environment },
    observe_hardware: { ...DEFAULT_REE_STEP_PARAMS.observe_hardware },
    generate_sbom: { ...DEFAULT_REE_STEP_PARAMS.generate_sbom },
    activate_experiment_environment: { ...DEFAULT_REE_STEP_PARAMS.activate_experiment_environment },
  };
}

export function mergeStepParams<K extends ReeStepKey>(
  stepParams: ReeStepParams,
  key: K,
  params: ReeStepRunParams<K>,
): ReeStepParams {
  return {
    ...stepParams,
    [key]: { ...stepParams[key], ...params },
  };
}
