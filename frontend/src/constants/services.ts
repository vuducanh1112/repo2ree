import { Ic } from "../components/Icon";
import type {
  Service,
  WorkflowServiceKey,
  WorkflowServiceParams,
  WorkflowServiceParamsByKey,
} from "../types";

type WorkflowService = Service & { key: WorkflowServiceKey };

export const SERVICES: WorkflowService[] = [
  {
    key: "evaluate",
    label: "Evaluate",
    IC: Ic.star,
    color: "#7c3aed",
    badge: { label: "Evaluated", color: "#7c3aed", bg: "#f5f3ff" },
    desc: "Get a quick reproducibility score for this repository. This scans the repository contents to assign a level.",
    requires: [{ field: "_sourceAvailable", label: "Source loaded in workspace" }],
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
    IC: Ic.cpu,
    color: "#0891b2",
    badge: { label: "Built", color: "#0891b2", bg: "#ecfeff" },
    desc: "Create the runnable environment for this project. This executes build_runtime_script to build the runtime from scratch.",
    requires: [
      { field: "_sourceAvailable", label: "Source available" },
      { field: "build_runtime_script", label: "Build script" },
    ],
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
    key: "sbom",
    label: "Generate SBOM",
    IC: Ic.package,
    color: "#16a34a",
    badge: { label: "SBOM ready", color: "#16a34a", bg: "#f0fdf4" },
    desc: "Generate a complete list of all software in your environment. This runs a dedicated sbom tool on the built runtime tarball and outputs an SPDX 2.3 SBOM.",
    requires: [{ field: "runtime", label: "Runtime" }],
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
    IC: Ic.shield,
    color: "#7c3aed",
    badge: { label: "Activation passed", color: "#7c3aed", bg: "#f5f3ff" },
    desc: "Check that the packaged environment actually starts and activates. This loads the runtime tarball and verifies activation succeeds by running the activation script.",
    requires: [{ field: "activation_script", label: "Activation script" }],
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

export function defaultParamsForService<K extends WorkflowServiceKey>(
  svc: Extract<WorkflowService, { key: K }>,
): WorkflowServiceParamsByKey[K] {
  return Object.fromEntries(
    (svc.params || []).map((p) => [p.key, p.default]),
  ) as WorkflowServiceParamsByKey[K];
}

export function initialServiceParams(): WorkflowServiceParams {
  return Object.fromEntries(
    SERVICES.map((svc) => [svc.key, defaultParamsForService(svc)]),
  ) as WorkflowServiceParams;
}

export function isWorkflowServiceKey(key: string): key is WorkflowServiceKey {
  return SERVICES.some((service) => service.key === key);
}
