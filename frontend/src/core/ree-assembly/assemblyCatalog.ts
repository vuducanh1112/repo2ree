import type { ReeAssemblyDefinition } from "./assemblyStepTypes";
import type {
  ReeAssemblyOperationKey,
  ReeAssemblyOperationParams,
  ReeAssemblyOperationParamsByKey,
  ReeAssemblyRunParams,
} from "./assemblyTypes";

type ReeAssemblyCatalogEntry = ReeAssemblyDefinition & { key: ReeAssemblyOperationKey };

export const REE_ASSEMBLY_STEPS: ReeAssemblyCatalogEntry[] = [
  {
    key: "evaluate",
    label: "Reproducibility Readiness",
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
    ],
  },
  {
    key: "build",
    label: "Build Runtime",
    iconKey: "cpu",
    color: "#0891b2",
    badge: { label: "Built", color: "#0891b2", bg: "#ecfeff" },
    desc: "Run the reserved build script and refresh the workspace after a successful build.",
    params: [],
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
    desc: "Check that the packaged environment actually starts and activates. This enters the runtime through its configured entry and runs the activation command, the same way experiments enter the runtime.",
    params: [],
  },
];

const DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS: ReeAssemblyOperationParams = {
  evaluate: { strict: false },
  build: {},
  hbom: {},
  sbom: { format: "spdx-json" },
  activation: {},
};

export function defaultParamsForReeAssemblyOperation<K extends ReeAssemblyOperationKey>(
  key: K,
): ReeAssemblyOperationParamsByKey[K] {
  return DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS[key];
}

export function initialReeAssemblyOperationParams(): ReeAssemblyOperationParams {
  return {
    evaluate: { ...DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS.evaluate },
    build: { ...DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS.build },
    hbom: { ...DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS.hbom },
    sbom: { ...DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS.sbom },
    activation: { ...DEFAULT_REE_ASSEMBLY_OPERATION_PARAMS.activation },
  };
}

export function mergeAssemblyOperationParams<K extends ReeAssemblyOperationKey>(
  stepParams: ReeAssemblyOperationParams,
  key: K,
  params: ReeAssemblyRunParams<K>,
): ReeAssemblyOperationParams {
  return {
    ...stepParams,
    [key]: { ...stepParams[key], ...params },
  };
}
