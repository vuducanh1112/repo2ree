// View model for the receipts console: the typed author evidence the backend
// carries inline (one latest successful receipt per operation). Nothing here
// derives new facts — it orders, labels and formats what the record states.
//
// Review receipts will land as a second section of the same console; keep the
// shapes below operation-agnostic so they can carry that evidence unchanged.

/** One rendered fact of a receipt's operation-specific payload. */
export interface ReceiptField {
  key: string;
  label: string;
  value: string;
  /** Full value when `value` is abbreviated (digests); empty otherwise. */
  title: string;
}

export interface ReceiptView {
  key: string;
  title: string;
  operation: string;
  runId: string;
  /** Compact duration label ("820ms", "12.400s", "3m 7s"). */
  duration: string;
  recordedAt: string;
  fields: ReceiptField[];
  /** The receipt exactly as recorded, for the raw view. */
  raw: unknown;
}

const OPERATION_LABELS: Record<string, string> = {
  acquire_source: "Source acquired",
  evaluate_reproducibility: "Reproducibility evaluated",
  observe_hardware: "Hardware observed",
  build_runtime: "Runtime built",
  generate_sbom: "SBOM generated",
  cross_check_sbom: "SBOM cross-check",
  activation_test: "Activation tested",
  run_experiment: "Experiment run",
};

// Pipeline order, so the console reads top-to-bottom like the canvas ring.
const OPERATION_ORDER: readonly string[] = [
  "acquire_source",
  "evaluate_reproducibility",
  "observe_hardware",
  "build_runtime",
  "generate_sbom",
  "cross_check_sbom",
  "activation_test",
  "run_experiment",
];

// The envelope every receipt shares — rendered by the card's own chrome, so
// the field list holds only what is specific to the operation.
const ENVELOPE_KEYS: ReadonlySet<string> = new Set([
  "schema_version",
  "operation",
  "run_id",
  "started_at",
  "finished_at",
  "duration_ms",
  "recorded_at",
]);

/**
 * Compact duration rendering, matching the backend's `format_duration_ms`
 * so a receipt reads the same in the console and in the operation log. Pure.
 */
export function formatReceiptDuration(durationMs: number): string {
  const ms = Math.max(0, Math.trunc(durationMs));
  const totalSeconds = Math.floor(ms / 1000);
  const milliseconds = ms % 1000;
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes) return `${minutes}m ${seconds}s`;
  if (totalSeconds) return `${totalSeconds}.${String(milliseconds).padStart(3, "0")}s`;
  return `${milliseconds}ms`;
}

/**
 * Defensively flatten a `ReeReceipts` payload into rendered receipt views.
 */
export function parseAuthorReceipts(value: unknown): ReceiptView[] {
  const raw = asRecord(value);
  if (!raw) return [];
  const experiments = asRecord(raw.experiments);
  const receipts = [
    raw.source,
    raw.evaluation,
    raw.hardware_observation,
    raw.build,
    raw.sbom,
    raw.sbom_cross_check,
    raw.test_activation,
    ...Object.values(experiments ?? {}),
  ];
  return receipts
    .map(parseReceipt)
    .filter((entry): entry is ReceiptView => entry !== null)
    .sort(compareReceipts);
}

function parseReceipt(value: unknown): ReceiptView | null {
  const receipt = asRecord(value);
  if (!receipt) return null;
  const operation = stringValue(receipt.operation);
  if (!operation) return null;

  return {
    key: `${operation}:${stringValue(receipt.run_id)}`,
    title: receiptTitle(operation, receipt),
    operation,
    runId: stringValue(receipt.run_id),
    duration:
      typeof receipt.duration_ms === "number" ? formatReceiptDuration(receipt.duration_ms) : "",
    recordedAt: stringValue(receipt.recorded_at),
    fields: receiptFields(receipt),
    raw: receipt,
  };
}

function receiptTitle(operation: string, receipt: Record<string, unknown>): string {
  const label = OPERATION_LABELS[operation] ?? operation;
  const experiment = stringValue(receipt.experiment_name);
  return experiment ? `${label} · ${experiment}` : label;
}

// The operation-specific payload, in the order the contract declares it.
function receiptFields(receipt: Record<string, unknown>): ReceiptField[] {
  return Object.entries(receipt)
    .filter(([key, value]) => !ENVELOPE_KEYS.has(key) && value !== null && value !== "")
    .map(([key, value]) => {
      const full = fieldValue(key, value);
      const shown = key.endsWith("_digest") ? abbreviate(full) : full;
      return {
        key,
        label: key.replace(/_/g, " "),
        value: shown,
        title: shown === full ? "" : full,
      };
    });
}

function fieldValue(key: string, value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (key === "workspace_drift") return workspaceDrift(value);
  return JSON.stringify(value) ?? "";
}

function workspaceDrift(value: unknown): string {
  const drift = asRecord(value);
  if (!drift) return "";
  const status = stringValue(drift.status) || "unknown";
  const count = typeof drift.changed_path_count === "number" ? drift.changed_path_count : 0;
  return count > 0 ? `${status} (${count} paths)` : status;
}

// Digests are the bulk of a receipt and never read in full at a glance; the
// card keeps the exact value in a tooltip.
function abbreviate(value: string): string {
  return value.length > 20 ? `${value.slice(0, 16)}…` : value;
}

function compareReceipts(left: ReceiptView, right: ReceiptView): number {
  const byOperation = operationRank(left.operation) - operationRank(right.operation);
  if (byOperation !== 0) return byOperation;
  return left.title.localeCompare(right.title);
}

function operationRank(operation: string): number {
  const index = OPERATION_ORDER.indexOf(operation);
  // Operations this build does not know about sort last, never interleaved.
  return index === -1 ? OPERATION_ORDER.length : index;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
