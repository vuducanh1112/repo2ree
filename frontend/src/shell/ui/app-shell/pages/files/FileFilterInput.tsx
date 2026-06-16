import { Ic } from "../../../shared/components/Icon";
import { lgColors, lgTree } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";

interface FileFilterInputProps {
  query: string;
  onChange: (q: string) => void;
  margin?: string | number;
}

export function FileFilterInput({ query, onChange, margin = "8px 8px 6px" }: FileFilterInputProps) {
  const filtering = query.trim().length > 0;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        margin,
        padding: "0 8px",
        borderRadius: 7,
        border: `1px solid ${lgTree.pane.borderColor}`,
        background: lgTree.inputBg,
      }}
    >
      <span style={{ display: "flex", color: lgColors.textMuted, flexShrink: 0 }}>
        {Ic.search(13)}
      </span>
      <input
        type="text"
        value={query}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Filter files…"
        aria-label="Filter files"
        style={{
          flex: 1,
          minWidth: 0,
          border: "none",
          outline: "none",
          background: "transparent",
          padding: "7px 0",
          fontSize: 12,
          fontFamily: F.sans,
          color: lgColors.text,
        }}
      />
      {filtering && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear filter"
          style={{
            display: "flex",
            alignItems: "center",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: lgColors.textMuted,
            padding: 2,
            flexShrink: 0,
          }}
        >
          {Ic.x(12)}
        </button>
      )}
    </div>
  );
}
