import type { AuthoringStepKey } from "../ree/AuthoringProgress";
import { type AppShellPage, PAGE } from "./pages";

const PAGE_BY_STEP: Readonly<Record<AuthoringStepKey, AppShellPage>> = {
  acquire_source: PAGE.ACQUIRE_SOURCE,
  metadata: PAGE.METADATA,
  observe_hardware: PAGE.OBSERVE_HARDWARE,
  evaluate_reproducibility: PAGE.EVALUATE_REPRODUCIBILITY,
  build_experiment_environment: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
  generate_sbom: PAGE.GENERATE_SBOM,
  cross_check_sbom: PAGE.GENERATE_SBOM,
  activate_experiment_environment: PAGE.ACTIVATE_EXPERIMENT_ENVIRONMENT,
  experiments: PAGE.EXPERIMENTS,
  seal_ree: PAGE.SEAL_REE,
};

export function authoringPageForStep(key: AuthoringStepKey): AppShellPage {
  return PAGE_BY_STEP[key];
}
