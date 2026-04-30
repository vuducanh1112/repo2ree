import type { AutomationStepDefinition } from "./WorkflowStepTypes";
import type {
  AutomationStepKey,
  AutomationStepParams,
  AutomationStepParamsByKey,
} from "./WorkflowTypes";

type WorkflowCatalogEntry = AutomationStepDefinition & { key: AutomationStepKey };

export const AUTOMATION_STEPS: WorkflowCatalogEntry[] = [
  {
    key: "evaluate",
    label: "Evaluate",
    iconKey: "star",
    color: "#7c3aed",
    badge: { label: "Evaluated", color: "#7c3aed", bg: "#f5f3ff" },
    desc: "Get a quick reproducibility score for this repository. This scans the repository contents to assign a level.",
    params: [
      {
        key: "strict",
        label: "Strict mode",
        type: "bool",
        default: false,
        hint: "Fail if any optional fields are missing",
      },
      {
        key: "swhid_check",
        label: "Check SWHID",
        type: "bool",
        default: true,
        hint: "Verify the SWHID is resolvable at Software Heritage",
      },
    ],
  },
  {
    key: "build",
    label: "Build Runtime",
    iconKey: "cpu",
    color: "#0891b2",
    badge: { label: "Built", color: "#0891b2", bg: "#ecfeff" },
    desc: "Create the runnable environment for this project. This executes build_runtime_script to build the runtime from scratch.",
    params: [
      {
        key: "no_cache",
        label: "No cache",
        type: "bool",
        default: true,
        hint: "Pass --no-cache to docker build",
      },
      {
        key: "platform",
        label: "Platform",
        type: "select",
        default: "linux/amd64",
        options: ["linux/amd64", "linux/arm64", "linux/arm/v7"],
        hint: "Target build platform",
      },
    ],
  },
  {
    key: "hbom",
    label: "Profile Machine",
    iconKey: "chip",
    color: "#0f766e",
    badge: { label: "HBOM profiled", color: "#0f766e", bg: "#ecfeff" },
    desc: "Inspect the current machine and prefill the HBOM with detected CPU, GPU, memory, storage, and network details.",
    params: [],
  },
  {
    key: "sbom",
    label: "Generate SBOM",
    iconKey: "package",
    color: "#16a34a",
    badge: { label: "SBOM ready", color: "#16a34a", bg: "#f0fdf4" },
    desc: "Generate a complete list of all software in your environment. This runs a dedicated sbom tool on the built runtime tarball and outputs an SPDX 2.3 SBOM.",
    params: [
      {
        key: "format",
        label: "Output format",
        type: "select",
        default: "spdx-json",
        options: ["spdx-json", "cyclonedx-json", "syft-json"],
        hint: "SBOM serialisation format",
      },
    ],
  },
  {
    key: "activation",
    label: "Test Activation",
    iconKey: "shield",
    color: "#7c3aed",
    badge: { label: "Activation passed", color: "#7c3aed", bg: "#f5f3ff" },
    desc: "Check that the packaged environment actually starts and activates. This loads the runtime tarball and verifies activation succeeds by running the activation script.",
    params: [
      {
        key: "timeout",
        label: "Timeout (s)",
        type: "text",
        default: "60",
        hint: "Max seconds to wait for container start",
      },
      {
        key: "verbose",
        label: "Verbose output",
        type: "bool",
        default: false,
        hint: "Print full stdout from container",
      },
    ],
  },
];

const DEFAULT_AUTOMATION_STEP_PARAMS: AutomationStepParams = {
  evaluate: { strict: false, swhid_check: true },
  build: { no_cache: true, platform: "linux/amd64" },
  hbom: {},
  sbom: { format: "spdx-json" },
  activation: { timeout: "60", verbose: false },
};

export function defaultParamsForAutomationStep<K extends AutomationStepKey>(
  key: K,
): AutomationStepParamsByKey[K] {
  return DEFAULT_AUTOMATION_STEP_PARAMS[key];
}

export function initialAutomationStepParams(): AutomationStepParams {
  return {
    evaluate: { ...DEFAULT_AUTOMATION_STEP_PARAMS.evaluate },
    build: { ...DEFAULT_AUTOMATION_STEP_PARAMS.build },
    hbom: { ...DEFAULT_AUTOMATION_STEP_PARAMS.hbom },
    sbom: { ...DEFAULT_AUTOMATION_STEP_PARAMS.sbom },
    activation: { ...DEFAULT_AUTOMATION_STEP_PARAMS.activation },
  };
}
