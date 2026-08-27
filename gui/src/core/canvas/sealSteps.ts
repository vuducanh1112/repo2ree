import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";

interface SealStepItem {
  key: string;
  label: string;
  done: boolean;
}

/**
 * What the seal freezes, step by step. `page` is the whole doneness rule: it
 * resolves through the same `resolveNavCompleted` the authoring rail and the
 * canvas nodes call, so this list cannot disagree with the step it names. The
 * union makes `done` unwritable beside a `page` — a step-backed entry cannot
 * grow a private predicate without first losing its step.
 */
type SealStepSpec = { key: string; label: string } & (
  | { page: AppShellPage; done?: never }
  | { page?: never; done: (ree: ReeEditorViewModel) => boolean }
);

const SEAL_STEPS: readonly SealStepSpec[] = [
  { key: PAGE.METADATA, label: "Metadata", page: PAGE.METADATA },
  { key: PAGE.HBOM, label: "HBOM", page: PAGE.HBOM },
  { key: PAGE.SOURCE, label: "Source", page: PAGE.SOURCE },
  { key: "runtime", label: "Runtime", page: PAGE.BUILD },
  // "Source identity", not "Software Heritage": the SWHID is computed locally
  // from the acquired tree and asserts nothing about any archive holding it.
  // The one entry that is not a step — there is no run, so no receipt to read.
  { key: "swh", label: "Source identity", done: (ree) => !!ree.spec.swhid },
  { key: "sbom", label: "SBOM", page: PAGE.SBOM },
  { key: "evaluate", label: "Reproducibility Readiness", page: PAGE.EVALUATE },
  { key: "experiments", label: "Experiments", page: PAGE.EXPERIMENTS },
  { key: "activation", label: "Test Activation", page: PAGE.ACTIVATION },
  // Deposit is deliberately absent. An archive accepting the bundle is not a
  // precondition of a complete REE — the Archive page says so itself — and an
  // entry that can never be done left the seal permanently "incomplete".
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
