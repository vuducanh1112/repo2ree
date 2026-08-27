/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { REE_STEPS } from "@core/ree-steps/stepCatalog";
import type { ReeStepKey } from "@core/ree-steps/stepRunParams";
import type { StepPageProps } from "@shell/ui/app-shell/pages/sharedStepUi";

export const exampleWorkspaceFiles = [
  { id: "runtime", name: "runtime.tar", type: "file" as const, size: 4096 },
  { id: "docker", name: "Dockerfile", type: "file" as const, content: "FROM python:3.12" },
  { id: "requirements", name: "requirements.txt", type: "file" as const, content: "requests" },
  {
    id: "overlay",
    name: "overlay",
    type: "folder" as const,
    children: [
      { id: "build", name: "build.sh", type: "file" as const, content: "#!/bin/sh\nexit 0" },
      { id: "activate", name: "activate.sh", type: "file" as const, content: "#!/bin/sh\nexit 0" },
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
    runtime: "runtime.tar",
    sbom: "artifacts/sbom.json",
    activation: {
      ...createEmptyReeEditorViewModel().spec.activation,
      runScript: "overlay/activate.sh",
      verifyScript: "overlay/verify.sh",
    },
  },
  source: { sourceAvailable: true, sourceIncluded: true },
  artifact: { runtimeIncluded: true },
  // A REE that has run its way through the pipeline: every receipt it carries
  // still speaks for what it declares. The cross-check is deliberately absent —
  // it is the one step this fixture has not run, so tests have a step that is
  // ready rather than complete.
  audit: {
    source: "current" as const,
    evaluation: "current" as const,
    hardware: "current" as const,
    runtime: "current" as const,
    sbom: "current" as const,
    test_activation: "current" as const,
  },
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
    artifactStatus: { runtimeIncluded: true },
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
    params: key === "evaluate" ? { strict: false } : {},
    setParam: () => {},
    ...overrides,
  };
}

export const scriptTemplateCatalog = {
  build: {
    path: "overlay/build.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
  activation: {
    run_script_path: "overlay/activate.sh",
    verify_script_path: "overlay/verify.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
  experiment: {
    run_script_path_pattern: "overlay/experiments/{slug}.sh",
    verify_script_path_pattern: "overlay/experiments/{slug}-verify.sh",
    templates: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
  },
  verify: [{ id: "default", label: "Default", body: "#!/bin/sh", is_default: true }],
};
