import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import { PROCESS_STEPS, resolveNavCompleted } from "@core/app-shell/processSteps";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";

interface SealCableItem {
  key: string;
  label: string;
  live: boolean;
}

/**
 * A cable is an authoring step unless it says otherwise, and `page` is the
 * whole liveness rule: it resolves through the same `resolveNavCompleted` the
 * rail and the canvas nodes call, so a cable cannot disagree with the node it
 * points at. The union makes `live` unwritable beside a `page` — a step-backed
 * cable cannot grow a private predicate without first losing its step.
 */
type SealCableSpec = { key: string; label: string } & (
  | { page: AppShellPage; live?: never }
  | { page?: never; live: (ree: ReeEditorViewModel) => boolean }
);

const SEAL_CABLES: readonly SealCableSpec[] = [
  { key: PAGE.METADATA, label: "Metadata", page: PAGE.METADATA },
  { key: PAGE.HBOM, label: "HBOM", page: PAGE.HBOM },
  { key: PAGE.SOURCE, label: "Source", page: PAGE.SOURCE },
  { key: "runtime", label: "Runtime", page: PAGE.BUILD },
  // "Source identity", not "Software Heritage": the SWHID is computed locally
  // from the acquired tree and asserts nothing about any archive holding it.
  // The one cable that is not a step — there is no run, so no receipt to read.
  { key: "swh", label: "Source identity", live: (ree) => !!ree.spec.swhid },
  { key: "sbom", label: "SBOM", page: PAGE.SBOM },
  { key: "evaluate", label: "Reproducibility Readiness", page: PAGE.EVALUATE },
  { key: "experiments", label: "Experiments", page: PAGE.EXPERIMENTS },
  { key: "activation", label: "Test Activation", page: PAGE.ACTIVATION },
  // Deposit is deliberately absent. An archive accepting the bundle is not a
  // precondition of a complete REE — the Archive page says so itself — and a
  // cable that can never go live left the seal permanently "incomplete".
];

const STEP_BY_PAGE = new Map(PROCESS_STEPS.map((step) => [step.key, step]));

export function buildSealCableItems(ree: ReeEditorViewModel, badges: Badges): SealCableItem[] {
  return SEAL_CABLES.map(({ key, label, page, live }) => {
    const step = page ? STEP_BY_PAGE.get(page) : undefined;
    return {
      key,
      label,
      live: step ? resolveNavCompleted(step, ree, badges) : !!live?.(ree),
    };
  });
}

export type { SealCableItem };
export { SEAL_CABLES };
