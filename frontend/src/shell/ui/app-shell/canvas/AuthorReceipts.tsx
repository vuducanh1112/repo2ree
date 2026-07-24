import type { AuthorReceiptEntry } from "@shell/data/receipts/queries";
import { C, F } from "../../theme/theme";

const OPERATION_LABELS = new Map<string, string>([
  ["acquire_source", "Source acquired"],
  ["snapshot_upstream", "Source snapshot"],
  ["build_runtime", "Runtime built"],
  ["generate_sbom", "SBOM generated"],
  ["cross_check_sbom", "SBOM cross-check"],
  ["activation_test", "Activation tested"],
]);

function receiptLabel(entry: AuthorReceiptEntry): string {
  if (entry.receipt.operation === "run_experiment") {
    return `Experiment · ${entry.receipt.experiment_name}`;
  }
  return OPERATION_LABELS.get(entry.receipt.operation) ?? entry.receipt.operation;
}

function freshnessColor(status: string): string {
  if (status === "fresh") return C.done;
  if (status === "stale") return "#d97706";
  return C.textMuted;
}

export function AuthorReceipts({ receipts }: { receipts: AuthorReceiptEntry[] }) {
  if (receipts.length === 0) {
    return (
      <div style={{ color: C.textMuted, fontSize: 10.5 }}>No author receipts recorded yet.</div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      {receipts.map((entry) => {
        const freshness = entry.consistency.status;
        const staleInputs = entry.consistency.stale_inputs ?? [];
        return (
          <details
            key={entry.key}
            style={{
              border: `1px solid ${C.border}`,
              borderRadius: 7,
              background: C.surface,
              overflow: "hidden",
            }}
          >
            <summary
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 8px",
                cursor: "pointer",
                listStyle: "none",
                fontFamily: F.mono,
                fontSize: 10,
              }}
            >
              <span style={{ flex: 1, color: C.textMid, fontWeight: 700 }}>
                {receiptLabel(entry)}
              </span>
              <span style={{ color: C.textMuted }}>{entry.receipt.run_id}</span>
              <span style={{ color: freshnessColor(freshness), fontWeight: 800 }}>
                {freshness.toUpperCase()}
              </span>
            </summary>
            {staleInputs.length > 0 && (
              <div
                style={{
                  padding: "5px 8px",
                  borderTop: `1px solid ${C.border}`,
                  color: "#b45309",
                  fontFamily: F.mono,
                  fontSize: 9.5,
                }}
              >
                Changed: {staleInputs.map((input) => input.input).join(", ")}
              </div>
            )}
            <pre
              style={{
                margin: 0,
                padding: 8,
                borderTop: `1px solid ${C.border}`,
                background: C.surfaceAlt,
                color: C.textMid,
                fontFamily: F.mono,
                fontSize: 9.5,
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere",
              }}
            >
              {JSON.stringify(entry.receipt, null, 2)}
            </pre>
          </details>
        );
      })}
    </div>
  );
}
