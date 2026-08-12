import type { ReceiptView } from "@core/receipts/authorReceipts";
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import styles from "./ReceiptCard.module.css";

// One materialised receipt: the operation it attests, when it ran and how
// long it took, and — on expand — its typed payload plus the raw JSON.
export function ReceiptCard({ receipt }: { receipt: ReceiptView }) {
  const [open, setOpen] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);

  return (
    <div className={styles.card}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className={styles.summary}
      >
        <span aria-hidden className={styles.chevron}>
          {open ? Ic.chevD(12) : Ic.chevR(12)}
        </span>
        <span className={styles.title}>{receipt.title}</span>
        {receipt.duration && <span className={styles.duration}>{receipt.duration}</span>}
      </button>

      {open && (
        <div className={styles.fields}>
          <Row label="run" value={receipt.runId} />
          <Row label="recorded" value={receipt.recordedAt} />
          {receipt.fields.map((field) => (
            <Row key={field.key} label={field.label} value={field.value} title={field.title} />
          ))}

          <button
            type="button"
            onClick={() => setRawOpen((value) => !value)}
            className={styles.rawToggle}
          >
            {rawOpen ? "hide raw receipt" : "raw receipt"}
          </button>
          {rawOpen && <pre className={styles.raw}>{JSON.stringify(receipt.raw, null, 2)}</pre>}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div className={styles.row}>
      <span className={styles.rowLabel}>{label}</span>
      <span title={title || value} className={styles.rowValue}>
        {value}
      </span>
    </div>
  );
}
