import type { ArchiveBinding, ReeIndexEntry } from "@core/ree-index/ReeIndexEntry";
import {
  archiveLabel,
  isDeposited,
  primaryBinding,
  shortDigest,
} from "@core/ree-index/ReeIndexEntry";
import { useReeIndex } from "@shell/data/ree-index/reeIndex";
import type React from "react";
import { useState } from "react";
import { Ic } from "../shared/components/Icon";
import { C, F } from "../theme/theme";

interface ReeIndexViewProps {
  onBack: () => void;
}

const COLS = "1.5fr 0.8fr 1.1fr 1.5fr" as const;

export function ReeIndexView({ onBack }: ReeIndexViewProps) {
  const [depositedOnly, setDepositedOnly] = useState(false);
  const {
    data: entries,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useReeIndex({
    depositedOnly,
  });

  return (
    <div style={{ minHeight: "100vh", background: C.bg, padding: 24, fontFamily: F.sans }}>
      <div style={{ maxWidth: 980, margin: "0 auto", animation: "fadeUp 0.4s ease" }}>
        <Header
          onBack={onBack}
          onRefresh={() => void refetch()}
          isFetching={isFetching}
          depositedOnly={depositedOnly}
          onToggleDepositedOnly={() => setDepositedOnly((current) => !current)}
        />

        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 14,
            boxShadow: "0 2px 12px rgba(0,0,0,0.05)",
            overflow: "hidden",
          }}
        >
          <HeaderRow />
          {isLoading ? (
            <StatusRow text="Loading index…" />
          ) : isError ? (
            <StatusRow
              text={`Failed to load the REE index: ${error instanceof Error ? error.message : "unknown error"}`}
              tone="error"
            />
          ) : !entries || entries.length === 0 ? (
            <EmptyState depositedOnly={depositedOnly} />
          ) : (
            entries.map((entry) => <EntryRow key={entry.subjectDigest} entry={entry} />)
          )}
        </div>
      </div>
    </div>
  );
}

function Header({
  onBack,
  onRefresh,
  isFetching,
  depositedOnly,
  onToggleDepositedOnly,
}: {
  onBack: () => void;
  onRefresh: () => void;
  isFetching: boolean;
  depositedOnly: boolean;
  onToggleDepositedOnly: () => void;
}) {
  const button: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 5,
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    padding: "7px 12px",
    color: C.textMid,
    fontSize: 13,
    cursor: "pointer",
  };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
      <button type="button" onClick={onBack} style={{ ...button, gap: 4 }}>
        {Ic.arrowLeft(15)} Back
      </button>
      <div style={{ flex: 1 }}>
        <h1
          style={{ fontSize: 22, fontWeight: 600, color: C.text, letterSpacing: -0.4, margin: 0 }}
        >
          REE Index
        </h1>
        <p style={{ fontSize: 13, color: C.textMuted, margin: "2px 0 0" }}>
          Sealed here, and where each one was deposited — kept after the workbench is gone
        </p>
      </div>
      <button
        type="button"
        onClick={onToggleDepositedOnly}
        title="Show only REEs an archive has issued an identifier for"
        style={{
          ...button,
          background: depositedOnly ? C.accentBg : C.surface,
          borderColor: depositedOnly ? C.accentBorder : C.border,
          color: depositedOnly ? C.accent : C.textMid,
        }}
      >
        {Ic.archive(15)} Deposited only
      </button>
      <button
        type="button"
        onClick={onRefresh}
        title="Refresh"
        style={{ ...button, opacity: isFetching ? 0.6 : 1 }}
      >
        {Ic.refresh(15)} Refresh
      </button>
    </div>
  );
}

function HeaderRow() {
  const cell: React.CSSProperties = {
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    color: C.textMuted,
  };
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: COLS,
        gap: 12,
        padding: "12px 18px",
        borderBottom: `1px solid ${C.border}`,
        background: C.surfaceAlt,
      }}
    >
      <div style={cell}>REE</div>
      <div style={cell}>Sealed</div>
      <div style={cell}>Archives</div>
      <div style={cell}>Identifier</div>
    </div>
  );
}

function EntryRow({ entry }: { entry: ReeIndexEntry }) {
  const primary = primaryBinding(entry);
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: COLS,
        gap: 12,
        padding: "14px 18px",
        borderBottom: `1px solid ${C.border}`,
        alignItems: "center",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span style={{ color: isDeposited(entry) ? C.done : C.textMuted, display: "flex" }}>
            {Ic.lock(15)}
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: C.text,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {entry.name || "—"}
          </span>
        </div>
        {/* The digest is the identity; the name is only a label, and two nodes
            can disagree about it while meaning the same REE. */}
        <div
          style={{ fontSize: 11, color: C.textMuted, fontFamily: F.mono, marginTop: 3 }}
          title={entry.subjectDigest}
        >
          {shortDigest(entry.subjectDigest)}
        </div>
      </div>

      {/* Date only; the full instant is a tooltip, since the column is scanned
          for "when roughly" rather than read to the second. */}
      <div style={{ fontSize: 12, color: C.textMid }} title={entry.sealedAt}>
        {entry.sealedAt.slice(0, 10) || "—"}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        {entry.archiveBindings.length === 0 ? (
          <span style={{ fontSize: 12, color: C.textMuted }}>Not deposited</span>
        ) : (
          entry.archiveBindings.map((binding) => (
            <ArchiveBadge key={`${binding.archive}:${binding.identifier}`} binding={binding} />
          ))
        )}
      </div>

      <div style={{ minWidth: 0 }}>
        {primary ? <Identifier binding={primary} /> : <span style={{ color: C.textMuted }}>—</span>}
      </div>
    </div>
  );
}

function ArchiveBadge({ binding }: { binding: ArchiveBinding }) {
  return (
    <span
      title={binding.identifier}
      style={{
        fontSize: 11,
        color: C.accent,
        background: C.accentBg,
        border: `1px solid ${C.accentBorder}`,
        borderRadius: 6,
        padding: "2px 7px",
        whiteSpace: "nowrap",
      }}
    >
      {archiveLabel(binding.archive)}
    </span>
  );
}

function Identifier({ binding }: { binding: ArchiveBinding }) {
  const text = (
    <span
      style={{
        fontSize: 12,
        color: binding.recordUrl ? C.accent : C.textMid,
        fontFamily: F.mono,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
    >
      {binding.identifier}
    </span>
  );
  // Only linkable when the archive told us where the record lives; an
  // identifier is not a URL, and guessing a resolver would invent a location
  // the deposit never claimed.
  if (!binding.recordUrl) {
    return text;
  }
  return (
    <a
      href={binding.recordUrl}
      target="_blank"
      rel="noreferrer"
      style={{ display: "flex", alignItems: "center", gap: 5, minWidth: 0, textDecoration: "none" }}
    >
      {text}
      <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
        {Ic.externalLink(12)}
      </span>
    </a>
  );
}

function StatusRow({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div
      style={{
        padding: "20px 18px",
        fontSize: 13,
        color: tone === "error" ? C.error : C.textMuted,
      }}
    >
      {text}
    </div>
  );
}

function EmptyState({ depositedOnly }: { depositedOnly: boolean }) {
  return (
    <div style={{ padding: "32px 18px", textAlign: "center" }}>
      <div
        style={{ color: C.textMuted, display: "flex", justifyContent: "center", marginBottom: 10 }}
      >
        {Ic.archive(24)}
      </div>
      <div style={{ fontSize: 14, fontWeight: 500, color: C.textMid, marginBottom: 4 }}>
        {depositedOnly ? "Nothing deposited yet" : "Nothing sealed yet"}
      </div>
      <div style={{ fontSize: 12, color: C.textMuted, lineHeight: 1.6 }}>
        {depositedOnly
          ? "Sealed REEs appear here once an archive issues an identifier for them."
          : "Sealing an REE records it here, where it stays after its workbench is torn down."}
      </div>
    </div>
  );
}
