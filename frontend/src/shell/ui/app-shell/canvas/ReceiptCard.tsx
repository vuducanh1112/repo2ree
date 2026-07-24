import type { ReceiptView } from "@core/receipts/authorReceipts";
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";

const FRESHNESS_COLOR: Record<string, string> = {
  fresh: C.done,
  stale: "#d97706",
  missing: C.textMuted,
};

const STATUS_COLOR: Record<string, string> = {
  succeeded: C.done,
  failed: C.error,
  canceled: C.textMuted,
};

// One materialised receipt: the operation it attests, when it ran and how
// long it took, whether the record still matches the current tree, and — on
// expand — its typed payload plus the raw JSON as recorded.
export function ReceiptCard({ receipt }: { receipt: ReceiptView }) {
  const [open, setOpen] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);

  return (
    <div
      style={{
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        background: C.surface,
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 7,
          width: "100%",
          padding: "6px 8px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: F.mono,
          fontSize: 10,
        }}
      >
        <span style={{ display: "flex", color: C.textMuted, flexShrink: 0 }}>
          {open ? Ic.chevD(12) : Ic.chevR(12)}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            color: C.textMid,
            fontWeight: 700,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {receipt.title}
        </span>
        {receipt.duration && (
          <span style={{ color: C.textMuted, flexShrink: 0 }}>{receipt.duration}</span>
        )}
        <span
          style={{
            color: FRESHNESS_COLOR[receipt.freshness] ?? C.textMuted,
            fontWeight: 800,
            flexShrink: 0,
          }}
        >
          {receipt.freshness.toUpperCase()}
        </span>
      </button>

      {open && (
        <div
          style={{
            borderTop: `1px solid ${C.border}`,
            padding: "7px 8px",
            display: "grid",
            gap: 5,
          }}
        >
          <Row label="run" value={receipt.runId} />
          <Row label="recorded" value={receipt.recordedAt} />
          <Row
            label="status"
            value={receipt.status}
            color={STATUS_COLOR[receipt.status] ?? C.textMid}
          />
          {receipt.fields.map((field) => (
            <Row key={field.key} label={field.label} value={field.value} title={field.title} />
          ))}

          {receipt.staleInputs.length > 0 && (
            <div
              style={{
                marginTop: 2,
                padding: "5px 6px",
                borderRadius: 6,
                background: "#fffbeb",
                border: "1px solid #fde68a",
                display: "grid",
                gap: 3,
              }}
            >
              {receipt.staleInputs.map((input) => (
                <div
                  key={input.input}
                  style={{
                    display: "flex",
                    gap: 6,
                    color: "#b45309",
                    fontFamily: F.mono,
                    fontSize: 9.5,
                  }}
                >
                  <span style={{ fontWeight: 700 }}>{input.input}</span>
                  <span style={{ flex: 1, textAlign: "right", overflow: "hidden" }}>
                    {input.recorded || "—"} → {input.current || "—"}
                  </span>
                </div>
              ))}
            </div>
          )}

          <button
            type="button"
            onClick={() => setRawOpen((value) => !value)}
            style={{
              justifySelf: "start",
              marginTop: 2,
              padding: 0,
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: C.textMuted,
              fontFamily: F.mono,
              fontSize: 9.5,
              textDecoration: "underline",
            }}
          >
            {rawOpen ? "hide raw receipt" : "raw receipt"}
          </button>
          {rawOpen && (
            <pre
              style={{
                margin: 0,
                maxHeight: 200,
                overflow: "auto",
                padding: 8,
                borderRadius: 6,
                background: C.surfaceAlt,
                color: C.textMid,
                fontFamily: F.mono,
                fontSize: 9.5,
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere",
              }}
            >
              {JSON.stringify(receipt.raw, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  title,
  color = C.textMid,
}: {
  label: string;
  value: string;
  title?: string;
  color?: string;
}) {
  return (
    <div style={{ display: "flex", gap: 8, fontFamily: F.mono, fontSize: 9.5 }}>
      <span style={{ width: 108, flexShrink: 0, color: C.textMuted }}>{label}</span>
      <span
        title={title || value}
        style={{ flex: 1, minWidth: 0, color, overflowWrap: "anywhere" }}
      >
        {value}
      </span>
    </div>
  );
}
