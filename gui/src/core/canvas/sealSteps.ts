import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";

interface SealStepItem {
  key: string;
  label: string;
  done: boolean;
}

type SealStepSpec = { key: string; label: string } & (
  | { page: AppShellPage; done?: never }
  | { page?: never; done: (ree: ReeEditorViewModel) => boolean }
);

const SEAL_STEPS: readonly SealStepSpec[] = [
  { key: PAGE.METADATA, label: "Metadata", page: PAGE.METADATA },
  { key: PAGE.OBSERVE_HARDWARE, label: "HBOM", page: PAGE.OBSERVE_HARDWARE },
  { key: PAGE.ACQUIRE_SOURCE, label: "Source", page: PAGE.ACQUIRE_SOURCE },
  {
    key: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
    label: "Experiment environment",
    page: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
  },
  { key: "swh", label: "Source identity", done: (ree) => !!ree.spec.swhid },
  { key: PAGE.GENERATE_SBOM, label: "SBOM", page: PAGE.GENERATE_SBOM },
  {
    key: PAGE.EVALUATE_REPRODUCIBILITY,
    label: "Reproducibility Readiness",
    page: PAGE.EVALUATE_REPRODUCIBILITY,
  },
  { key: "experiments", label: "Experiments", page: PAGE.EXPERIMENTS },
  {
    key: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
    label: "Test Activation",
    page: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
  },
];

const STEP_BY_PAGE = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

export function buildSealStepItems(ree: ReeEditorViewModel, badges: Badges): SealStepItem[] {
  return SEAL_STEPS.map(({ key, label, page, done }) => {
    const step = page ? STEP_BY_PAGE.get(page) : undefined;
    return {
      key,
      label,
      done: step ? resolveNavCompleted(step, ree, badges) : !!done?.(ree),
    };
  });
}

export { SEAL_STEPS };
