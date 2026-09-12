import { useOperationHistoryQuery } from "@shell/data/history/queries";
import styles from "./OperationHistorySection.module.css";

export function OperationHistorySection({ enabled }: { enabled: boolean }) {
  const history = useOperationHistoryQuery(enabled);
  return (
    <section className={styles.section} aria-label="Operation history">
      <h3 className={styles.heading}>Operation history</h3>
      <button
        type="button"
        className={styles.refresh}
        disabled={!enabled || history.isFetching}
        onClick={() => void history.refetch()}
      >
        Refresh history
      </button>
      {history.isLoading && enabled && <p>Loading operation history…</p>}
      {history.isError && <p role="alert">Could not load operation history.</p>}
      {history.data?.operations?.length === 0 && <p>No operations recorded yet.</p>}
      {history.data?.operations?.map((record) => (
        <details key={record.attempt_id} className={styles.card}>
          <summary className={styles.summary}>
            {record.sequence != null ? `#${record.sequence} ` : "Unordered · "}
            {String(record.command.operation ?? "Operation")} · {record.operation_status}
          </summary>
          <div className={styles.body}>
            <div>Scope: {record.scope === "." ? "Author" : record.scope}</div>
            <div>Run: {record.run_id}</div>
            <div>Capture: {record.capture_status}</div>
            {record.capture_status === "pending" && (
              <p>Capture is incomplete; completion may be unresolved.</p>
            )}
            <div>Before: {record.before_snapshot_id ?? "Not captured"}</div>
            <div>After: {record.after_snapshot_id ?? "Not captured"}</div>
            {record.operation_failure && <p>{record.operation_failure.message}</p>}
            {record.capture_error && <p>{record.capture_error}</p>}
            <details>
              <summary>Command and raw record</summary>
              <pre className={styles.raw}>{JSON.stringify(record, null, 2)}</pre>
            </details>
          </div>
        </details>
      ))}
    </section>
  );
}
