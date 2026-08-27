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

/** Full backend verdict for one authoring operation. */
export interface StepAudit {
  evidence: EvidenceStatus;
  payload: "missing" | "present" | "stale" | "not_applicable";
  receiptRunId?: string;
  reasons: string[];
}

export interface ExperimentAudit {
  name: string;
  run: StepAudit;
}

/**
 * The complete audit returned with an REE. Unlike the legacy StepEvidence
 * projection this retains the receipt/run binding and the backend's reasons.
 */
export interface ReeAudit {
  source?: StepAudit | EvidenceStatus;
  evaluation?: StepAudit | EvidenceStatus;
  hardware?: StepAudit | EvidenceStatus;
  runtime?: StepAudit | EvidenceStatus;
  sbom?: StepAudit | EvidenceStatus;
  sbom_cross_check?: StepAudit | EvidenceStatus;
  test_activation?: StepAudit | EvidenceStatus;
  experiments?: ExperimentAudit[];
}

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

function mapRawStepAudit(raw: unknown): StepAudit {
  const entry = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const evidence = EVIDENCE_STATUSES.includes(entry.evidence as EvidenceStatus)
    ? (entry.evidence as EvidenceStatus)
    : "missing";
  const payloadStatuses = ["missing", "present", "stale", "not_applicable"] as const;
  const payload = payloadStatuses.includes(entry.payload as (typeof payloadStatuses)[number])
    ? (entry.payload as StepAudit["payload"])
    : "missing";
  return {
    evidence,
    payload,
    receiptRunId: entry.receipt_run_id ? String(entry.receipt_run_id) : undefined,
    reasons: Array.isArray(entry.reasons) ? entry.reasons.map(String) : [],
  };
}

export function mapRawReeAudit(raw: unknown): ReeAudit {
  const audit = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const mapped: ReeAudit = { experiments: [] };
  for (const step of EVIDENCE_STEPS) {
    mapped[step] = mapRawStepAudit(audit[step]);
  }
  mapped.experiments = Array.isArray(audit.experiments)
    ? audit.experiments.map((value) => {
        const experiment =
          value && typeof value === "object" ? (value as Record<string, unknown>) : {};
        return { name: String(experiment.name ?? ""), run: mapRawStepAudit(experiment.run) };
      })
    : [];
  return mapped;
}

function auditEvidence(audit: ReeAudit, step: EvidenceStep): EvidenceStatus {
  const entry = audit[step];
  return typeof entry === "string" ? entry : (entry?.evidence ?? "missing");
}

export function auditReceiptRunId(audit: ReeAudit, step: EvidenceStep): string | undefined {
  const entry = audit[step];
  return typeof entry === "string" ? undefined : entry?.receiptRunId;
}

export function isAuditCurrent(audit: ReeAudit, step: EvidenceStep): boolean {
  return auditEvidence(audit, step) === "current";
}

export function isAuditStale(audit: ReeAudit, step: EvidenceStep): boolean {
  return auditEvidence(audit, step) === "stale";
}
