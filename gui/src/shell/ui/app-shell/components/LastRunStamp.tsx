import styles from "./LastRunStamp.module.css";

export function LastRunStamp({ label, ts }: { label: string; ts: string }) {
  return (
    <span className={styles.stamp}>
      {label}{" "}
      {new Date(ts).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}
