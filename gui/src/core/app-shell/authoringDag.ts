import type { AuthoringStepKey } from "../ree/AuthoringProgress";
import { type AppShellPage, PAGE } from "./pages";

const PAGE_BY_STEP: Readonly<Record<AuthoringStepKey, AppShellPage>> = {
  source: PAGE.SOURCE,
  metadata: PAGE.METADATA,
  hbom: PAGE.HBOM,
  evaluate: PAGE.EVALUATE,
  // biome-ignore lint/style/useNamingConvention: an authoring step key, as the REE names it
  build_experiment_environment: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
  sbom: PAGE.SBOM,
  // The cross-check is the second operation on the SBOM page.
  crosscheck: PAGE.SBOM,
  activation: PAGE.ACTIVATION,
  experiments: PAGE.EXPERIMENTS,
  seal: PAGE.SEAL,
};

export function authoringPageForStep(key: AuthoringStepKey): AppShellPage {
  return PAGE_BY_STEP[key];
}
