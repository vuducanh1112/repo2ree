/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import type { ReeStepKey } from "@core/ree-steps/stepRunParams";
import type { StepPageProps } from "@shell/ui/app-shell/pages/sharedStepUi";
import { authoringProgress } from "./authoringProgress";

export const exampleWorkspaceFiles = [
  { id: "experiment_environment", name: "runtime.tar", type: "file" as const, size: 4096 },
  { id: "docker", name: "Dockerfile", type: "file" as const, content: "FROM python:3.12" },
  { id: "requirements", name: "requirements.txt", type: "file" as const, content: "requests" },
  {
    id: "overlay",
    name: "overlay",
    type: "folder" as const,
    children: [
      {
        id: "build_experiment_environment",
        name: "build.sh",
        type: "file" as const,
        content: "#!/bin/sh\nexit 0",
      },
      {
        id: "activate",
        name: "activate.sh",
        type: "file" as const,
        content: '#!/bin/sh\nexec "$@"',
      },
      { id: "verify", name: "verify.sh", type: "file" as const, content: "#!/bin/sh\nexit 0" },
    ],
  },
];

export const exampleEditorRee = {
  ...createEmptyReeEditorViewModel(),
  spec: {
    ...createEmptyReeEditorViewModel().spec,
    name: "Python hello world",
    catalogMetadata: {
      ...createEmptyReeEditorViewModel().spec.catalogMetadata,
      version: "1.0.0",
      description: "Prints hello world, reproducibly.",
    },
    experimentEnvironmentPath: "runtime.tar",
    sbom: "artifacts/sbom.json",
  },
  source: { sourceAvailable: true, sourceIncluded: true },
  artifact: { experimentEnvironmentIncluded: true },
  audit: {
    acquire_source: "current" as const,
    evaluate_reproducibility: "current" as const,
    observe_hardware: "current" as const,
    build_experiment_environment: "current" as const,
    generate_sbom: "current" as const,
    activate_experiment_environment: "current" as const,
  },
  steps: authoringProgress(
    {
      acquire_source: "complete",
      metadata: "complete",
      observe_hardware: "ready",
      evaluate_reproducibility: "complete",
      build_experiment_environment: "complete",
      generate_sbom: "complete",
      cross_check_sbom: "ready",
      activate_experiment_environment: "complete",
      experiments: "ready",
      seal_ree: "ready",
    },
    "observe_hardware",
  ),
};

export function createStepPageProps(
  key: ReeStepKey,
  overrides: Partial<StepPageProps> = {},
): StepPageProps {
  const step = REE_STEPS.find((candidate) => candidate.key === key);
  if (!step) throw new Error(`Missing step fixture: ${key}`);
  return {
    step,
    ree: exampleEditorRee,
    workspaceSourceState: { sourceAvailable: true, sourceIncluded: true },
    artifactStatus: { experimentEnvironmentIncluded: true },
    evaluationState: { dependencyLevel: 2, environmentLevel: 2, machineLevel: 1 },
    badges: {},
    workspaceFiles: exampleWorkspaceFiles,
    reeFiles: [
      {
        id: "sbom",
        name: "artifacts/sbom.json",
        type: "file",
        tag: "Artifact",
        content: JSON.stringify({ bomFormat: "CycloneDX", components: [{ name: "requests" }] }),
      },
    ],
    log: null,
    running: false,
    runDone: false,
    runFailed: false,
    badge: null,
    ts: undefined,
    onRun: () => {},
    onCancel: () => {},
    onGo: () => {},
    onGoFields: () => {},
    onReeSpecChange: () => {},
    onPersistWorkspaceFile: async () => {},
    missing: [],
    params: key === "evaluate_reproducibility" ? { strict: false } : {},
    setParam: () => {},
    ...overrides,
  };
}

export const scriptTemplateCatalog = {
  activate_experiment_environment: {
    path: "overlay/activate.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
  build_experiment_environment: {
    path: "overlay/build.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
  experiment_run: {
    path_pattern: "overlay/experiments/{slug}.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
  experiment_verify: {
    path_pattern: "overlay/experiments/{slug}-verify.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
};
