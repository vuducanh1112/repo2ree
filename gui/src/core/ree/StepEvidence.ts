import { requireKnownNames } from "@core/contract/unknownNames";
import { REE_AUDIT_KEYS, type ReeAuditKey } from "@core/generated/vocabulary";

export type EvidenceStatus = "missing" | "current" | "stale" | "not_applicable";

export type EvidenceStep = Exclude<ReeAuditKey, "experiments">;

const EVIDENCE_STEPS = REE_AUDIT_KEYS.filter((key): key is EvidenceStep => key !== "experiments");

export type StepEvidence = Partial<Record<EvidenceStep, EvidenceStatus>>;

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

export type ReeAudit = Partial<Record<EvidenceStep, StepAudit | EvidenceStatus>> & {
  experiments?: ExperimentAudit[];
};

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

export function isEvidenceCurrent(evidence: StepEvidence, step: EvidenceStep): boolean {
  return evidenceOf(evidence, step) === "current";
}

export function isEvidenceStale(evidence: StepEvidence, step: EvidenceStep): boolean {
  return evidenceOf(evidence, step) === "stale";
}

function auditRecord(raw: unknown): Record<string, unknown> {
  const audit = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  requireKnownNames("audit", REE_AUDIT_KEYS, Object.keys(audit));
  return audit;
}

export function mapRawStepEvidence(raw: unknown): StepEvidence {
  const audit = auditRecord(raw);
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
  const audit = auditRecord(raw);
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

export function auditReceiptRunIds(audit: ReeAudit): Set<string> {
  const runIds = [
    ...EVIDENCE_STEPS.map((step) => auditReceiptRunId(audit, step)),
    ...(audit.experiments ?? []).map((experiment) => experiment.run.receiptRunId),
  ];
  return new Set(runIds.filter((runId): runId is string => !!runId));
}

export function isAuditCurrent(audit: ReeAudit, step: EvidenceStep): boolean {
  return auditEvidence(audit, step) === "current";
}

export function isAuditStale(audit: ReeAudit, step: EvidenceStep): boolean {
  return auditEvidence(audit, step) === "stale";
}
