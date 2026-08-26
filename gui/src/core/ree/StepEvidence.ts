// Whether the receipt this REE carries for one step still speaks for what the
// REE now declares. This is the backend's verdict — the `ReeAudit` shipped with
// every REE document — not a record that a run happened in this browser tab:
// editing a build script leaves the build receipt in place but makes it
// `stale`. The vocabulary mirrors `StepAudit.evidence` in
// core/domain/ree/audit.py; keep the two spellings identical.
export type EvidenceStatus = "missing" | "current" | "stale" | "not_applicable";

/** The audit's own step names. The domain names its steps; pages are the shell's word. */
export type EvidenceStep =
  | "source"
  | "evaluation"
  | "hardware"
  | "runtime"
  | "sbom"
  | "sbom_cross_check"
  | "test_activation";

export type StepEvidence = Partial<Record<EvidenceStep, EvidenceStatus>>;

const EVIDENCE_STEPS: readonly EvidenceStep[] = [
  "source",
  "evaluation",
  "hardware",
  "runtime",
  "sbom",
  "sbom_cross_check",
  "test_activation",
];

const EVIDENCE_STATUSES: readonly EvidenceStatus[] = [
  "missing",
  "current",
  "stale",
  "not_applicable",
];

export function createEmptyStepEvidence(): StepEvidence {
  return {};
}

function evidenceOf(evidence: StepEvidence, step: EvidenceStep): EvidenceStatus {
  return evidence[step] ?? "missing";
}

/**
 * A step counts as done only while its receipt still holds. `stale` is
 * deliberately not done: the receipt describes inputs that have since moved, so
 * the step has to run again before anything may build on it.
 */
export function isEvidenceCurrent(evidence: StepEvidence, step: EvidenceStep): boolean {
  return evidenceOf(evidence, step) === "current";
}

export function isEvidenceStale(evidence: StepEvidence, step: EvidenceStep): boolean {
  return evidenceOf(evidence, step) === "stale";
}

/**
 * Project the wire `ReeAudit` (a `StepAudit` per step) down to the standing we
 * read. Payload and reasons stay on the wire: nothing here reports on a bundle.
 */
export function mapRawStepEvidence(raw: unknown): StepEvidence {
  const audit = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const evidence: StepEvidence = {};
  for (const step of EVIDENCE_STEPS) {
    const entry = audit[step];
    const status =
      entry && typeof entry === "object" ? (entry as Record<string, unknown>).evidence : undefined;
    if (EVIDENCE_STATUSES.includes(status as EvidenceStatus)) {
      evidence[step] = status as EvidenceStatus;
    }
  }
  return evidence;
}
