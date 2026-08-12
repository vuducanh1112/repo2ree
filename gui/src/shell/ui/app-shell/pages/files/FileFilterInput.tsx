import { Ic } from "@shell/ui/shared/components/Icon";
import { cssVars } from "@shell/ui/theme/styleVars";
import styles from "./FilesPage.module.css";

interface FileFilterInputProps {
  query: string;
  onChange: (q: string) => void;
  /** Where the pane places the control; a measurement, so it rides a custom
   * property rather than a class. */
  margin?: string | number;
}

export function FileFilterInput({ query, onChange, margin }: FileFilterInputProps) {
  const filtering = query.trim().length > 0;
  return (
    <div
      className={styles.filter}
      style={cssVars(margin === undefined ? {} : { "--filter-margin": margin })}
    >
      <span aria-hidden className={styles.filterIcon}>
        {Ic.search(13)}
      </span>
      <input
        type="text"
        value={query}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Filter files…"
        aria-label="Filter files"
        className={styles.filterInput}
      />
      {filtering && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear filter"
          className={styles.clear}
        >
          {Ic.x(12)}
        </button>
      )}
    </div>
  );
}
