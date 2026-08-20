import type { ArchiveBinding, ReeIndexEntry } from "@core/ree-index/ReeIndexEntry";
import {
  archiveLabel,
  isDeposited,
  primaryBinding,
  shortDigest,
} from "@core/ree-index/ReeIndexEntry";
import { useReeIndex } from "@shell/data/ree-index/reeIndex";
import { useState } from "react";
import { Ic } from "../shared/components/Icon";
import styles from "./ReeIndexView.module.css";

interface ReeIndexViewProps {
  onBack: () => void;
}

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
    <main className={styles.screen}>
      <div className={styles.column}>
        <Header
          onBack={onBack}
          onRefresh={() => void refetch()}
          isFetching={isFetching}
          depositedOnly={depositedOnly}
          onToggleDepositedOnly={() => setDepositedOnly((current) => !current)}
        />

        <div className={styles.table}>
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
    </main>
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
  return (
    <div className={styles.header}>
      <button type="button" onClick={onBack} className={styles.chromeButton}>
        {Ic.arrowLeft(15)} Back
      </button>
      <div className={styles.headings}>
        <h1 className={styles.title}>REE Index</h1>
        <p className={styles.subtitle}>
          Sealed here, and where each one was deposited — kept after the workbench is gone
        </p>
      </div>
      <button
        type="button"
        onClick={onToggleDepositedOnly}
        aria-pressed={depositedOnly}
        title="Show only REEs an archive has issued an identifier for"
        className={styles.chromeButton}
      >
        {Ic.archive(15)} Deposited only
      </button>
      <button
        type="button"
        onClick={onRefresh}
        title="Refresh"
        className={styles.chromeButton}
        data-busy={isFetching || undefined}
      >
        {Ic.refresh(15)} Refresh
      </button>
    </div>
  );
}

function HeaderRow() {
  return (
    <div className={styles.row} data-kind="head">
      <div className={styles.headCell}>REE</div>
      <div className={styles.headCell}>Sealed</div>
      <div className={styles.headCell}>Archives</div>
      <div className={styles.headCell}>Identifier</div>
    </div>
  );
}

function EntryRow({ entry }: { entry: ReeIndexEntry }) {
  const primary = primaryBinding(entry);
  return (
    <div className={styles.row}>
      <div className={styles.subject}>
        <div className={styles.subjectName}>
          <span
            aria-hidden
            className={styles.sealIcon}
            data-deposited={isDeposited(entry) || undefined}
          >
            {Ic.lock(15)}
          </span>
          <span className={styles.name}>{entry.name || "—"}</span>
        </div>
        <div className={styles.digest} title={entry.subjectDigest}>
          {shortDigest(entry.subjectDigest)}
        </div>
      </div>

      {/* Date only; the full instant is a tooltip, since the column is scanned
          for "when roughly" rather than read to the second. */}
      <div className={styles.cell} title={entry.sealedAt}>
        {entry.sealedAt.slice(0, 10) || "—"}
      </div>

      <div className={styles.archives}>
        {entry.archiveBindings.length === 0 ? (
          <span className={styles.muted}>Not deposited</span>
        ) : (
          entry.archiveBindings.map((binding) => (
            <ArchiveBadge key={`${binding.archive}:${binding.identifier}`} binding={binding} />
          ))
        )}
      </div>

      <div className={styles.subject}>
        {primary ? <Identifier binding={primary} /> : <span className={styles.muted}>—</span>}
      </div>
    </div>
  );
}

function ArchiveBadge({ binding }: { binding: ArchiveBinding }) {
  return (
    <span title={binding.identifier} className={styles.archiveBadge}>
      {archiveLabel(binding.archive)}
    </span>
  );
}

function Identifier({ binding }: { binding: ArchiveBinding }) {
  const text = (
    <span className={styles.identifier} data-linked={binding.recordUrl ? true : undefined}>
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
    <a href={binding.recordUrl} target="_blank" rel="noreferrer" className={styles.recordLink}>
      {text}
      <span aria-hidden className={styles.externalIcon}>
        {Ic.externalLink(12)}
      </span>
    </a>
  );
}

function StatusRow({ text, tone }: { text: string; tone?: "error" }) {
  return (
    <div className={styles.statusRow} data-tone={tone}>
      {text}
    </div>
  );
}

function EmptyState({ depositedOnly }: { depositedOnly: boolean }) {
  return (
    <div className={styles.empty}>
      <div aria-hidden className={styles.emptyIcon}>
        {Ic.archive(24)}
      </div>
      <div className={styles.emptyTitle}>
        {depositedOnly ? "Nothing deposited yet" : "Nothing sealed yet"}
      </div>
      <div className={styles.emptyHint}>
        {depositedOnly
          ? "Sealed REEs appear here once an archive issues an identifier for them."
          : "Sealing an REE records it here, where it stays after its workbench is torn down."}
      </div>
    </div>
  );
}
