import type { ActionReceipt } from "../../../../../core/ree/ReeTypes";
import { Ic } from "../../../shared/components/Icon";
import { lgBackgrounds, lgColors, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/tokens";
import { GlassPageHeader } from "../../components/GlassPageHeader";

interface ProvenancePageProps {
  receipts: ActionReceipt[];
  loading: boolean;
}

const STATUS_COLOR: Record<ActionReceipt["status"], string> = {
  succeeded: lgColors.success,
  failed: lgColors.danger,
  canceled: lgColors.warning,
};

const STATUS_BG: Record<ActionReceipt["status"], string> = {
  succeeded: lgBackgrounds.success,
  failed: lgBackgrounds.danger,
  canceled: lgBackgrounds.draft,
};

function formatDuration(startedAt: string, finishedAt: string): string {
  const diff = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  if (Number.isNaN(diff) || diff < 0) return "—";
  if (diff < 1000) return `${diff} ms`;
  return `${(diff / 1000).toFixed(1)} s`;
}

function shortDigest(digest: string): string {
  const hex = digest.replace(/^sha256:/, "");
  return `${hex.slice(0, 8)}…`;
}

type ElidedStub = { __elided__: true; sha256: string; bytes: number };

function isElidedStub(v: unknown): v is ElidedStub {
  return typeof v === "object" && v !== null && "__elided__" in v;
}

function renderArgValue(value: unknown): string {
  if (isElidedStub(value)) {
    return `[${value.bytes} bytes, ${shortDigest(value.sha256)}]`;
  }
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function CommandArgs({ command }: { command: Record<string, unknown> }) {
  const args = command.args;
  if (!args || typeof args !== "object" || Array.isArray(args)) return null;
  const entries = Object.entries(args as Record<string, unknown>);
  if (entries.length === 0) return null;

  return (
    <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 2 }}>
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: "flex", gap: 6 }}>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 11,
              color: lgColors.textMuted,
              flexShrink: 0,
            }}
          >
            {k}:
          </span>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 11,
              color: isElidedStub(v) ? lgColors.textMuted : lgColors.text,
              wordBreak: "break-all",
              fontStyle: isElidedStub(v) ? "italic" : undefined,
            }}
            title={typeof v === "string" ? v : undefined}
          >
            {renderArgValue(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ProvenancePage({ receipts, loading }: ProvenancePageProps) {
  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.layers(24)}
          iconTint={{
            color: lgColors.indigo,
            border: `${lgColors.indigo}55`,
            shadow: `${lgColors.indigo}30`,
          }}
          title="Provenance"
          subtitle="Replayable journal of the structural operations that built this REE."
          badges={
            <span
              style={{
                padding: "3px 10px",
                borderRadius: 999,
                fontSize: 11,
                fontFamily: F.sans,
                fontWeight: 600,
                background: lgBackgrounds.chip,
                color: lgColors.chipText,
                border: "1px solid rgba(79,70,229,0.28)",
              }}
            >
              {receipts.length} {receipts.length === 1 ? "entry" : "entries"}
            </span>
          }
        />

        <div style={{ ...lgStyles.panel, overflow: "hidden", marginBottom: 16 }}>
          {loading && (
            <div
              style={{
                padding: "32px 24px",
                textAlign: "center",
                color: lgColors.textMuted,
                fontSize: 13,
                fontFamily: F.sans,
              }}
            >
              {Ic.loader(18)} Loading…
            </div>
          )}

          {!loading && receipts.length === 0 && (
            <div
              style={{
                padding: "40px 24px",
                textAlign: "center",
                color: lgColors.textMuted,
                fontSize: 13,
                fontFamily: F.sans,
              }}
            >
              No structural operations recorded yet. Run Evaluate, Build, or Seal to begin.
            </div>
          )}

          {!loading && receipts.length > 0 && (
            <div>
              {receipts.map((receipt, idx) => (
                <ReceiptRow
                  key={receipt.receipt_id}
                  receipt={receipt}
                  index={idx}
                  isLast={idx === receipts.length - 1}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface ReceiptRowProps {
  receipt: ActionReceipt;
  index: number;
  isLast: boolean;
}

function ReceiptRow({ receipt, isLast }: ReceiptRowProps) {
  const statusColor = STATUS_COLOR[receipt.status];
  const statusBg = STATUS_BG[receipt.status];
  const duration = formatDuration(receipt.started_at, receipt.finished_at);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "14px 20px",
        borderBottom: isLast ? "none" : "1px solid rgba(148, 163, 184, 0.2)",
      }}
    >
      {/* Timeline dot */}
      <div
        style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 2 }}
      >
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: statusColor,
            flexShrink: 0,
            marginTop: 3,
          }}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {/* Operation chip */}
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 12,
              fontWeight: 600,
              color: lgColors.text,
              background: lgBackgrounds.chip,
              border: "1px solid rgba(79,70,229,0.2)",
              borderRadius: 6,
              padding: "2px 8px",
            }}
          >
            {receipt.operation}
          </span>

          {/* Status badge */}
          <span
            style={{
              fontFamily: F.sans,
              fontSize: 11,
              fontWeight: 600,
              color: statusColor,
              background: statusBg,
              border: `1px solid ${statusColor}44`,
              borderRadius: 999,
              padding: "2px 8px",
            }}
          >
            {receipt.status}
          </span>

          {/* Duration */}
          <span style={{ fontFamily: F.mono, fontSize: 11, color: lgColors.textMuted }}>
            {duration}
          </span>
        </div>

        {/* Command args — the replay payload */}
        {receipt.command && <CommandArgs command={receipt.command} />}

        {/* Timestamps and digest */}
        <div
          style={{
            display: "flex",
            gap: 16,
            marginTop: 6,
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontFamily: F.mono, fontSize: 11, color: lgColors.textMuted }}>
            {new Date(receipt.started_at).toLocaleString([], {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </span>
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 11,
              color: lgColors.textMuted,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
            title={receipt.action_digest}
          >
            action: {shortDigest(receipt.action_digest)}
          </span>
          {receipt.input_digest && (
            <span
              style={{ fontFamily: F.mono, fontSize: 11, color: lgColors.textMuted }}
              title={receipt.input_digest}
            >
              in: {shortDigest(receipt.input_digest)}
            </span>
          )}
          {receipt.output_digest && (
            <span
              style={{ fontFamily: F.mono, fontSize: 11, color: lgColors.textMuted }}
              title={receipt.output_digest}
            >
              out: {shortDigest(receipt.output_digest)}
            </span>
          )}
          {receipt.predecessor && (
            <span style={{ fontFamily: F.mono, fontSize: 11, color: lgColors.textMuted }}>
              ← {receipt.predecessor.slice(0, 8)}
            </span>
          )}
        </div>

        {/* Failed outputs / exit code */}
        {receipt.status !== "succeeded" && receipt.exit_code !== 0 && (
          <div
            style={{
              marginTop: 6,
              fontFamily: F.mono,
              fontSize: 11,
              color: lgColors.danger,
            }}
          >
            exit {receipt.exit_code}
          </div>
        )}
      </div>
    </div>
  );
}
