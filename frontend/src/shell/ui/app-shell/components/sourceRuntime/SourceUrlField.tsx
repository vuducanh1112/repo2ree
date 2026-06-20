import { Ic } from "@shell/ui/shared/components/Icon";
import { C, F, S_SOURCE_URL_STATUS_BASE } from "@shell/ui/theme/theme";
import { inp } from "./shared";

interface SourceUrlFieldProps {
  locked: boolean;
  /** Live URL value, owned by the parent so a single Download button can act on it. */
  value: string;
  /** Previously committed origin, used to warn that a change resets downstream results. */
  priorValue?: string;
  onChange: (value: string) => void;
  onFocus?: () => void;
}

const URL_PATTERN = /^https?:\/\/[^\s]+$/i;

export function isLikelySourceUrl(value: string): boolean {
  return URL_PATTERN.test(value.trim());
}

// Plain controlled input — no separate "check reachable" step. Reachability is
// validated as part of the single Download action in the parent, so typing a URL
// and pressing Download is the whole flow.
export function SourceUrlField({
  locked,
  value,
  priorValue,
  onChange,
  onFocus,
}: SourceUrlFieldProps) {
  const trimmed = value.trim();
  const valid = isLikelySourceUrl(value);
  const prior = (priorValue || "").trim();
  const changesPrior = !!prior && trimmed !== prior;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ flex: 1, position: "relative" }}>
        <div
          style={{
            position: "absolute",
            left: 10,
            top: "50%",
            transform: "translateY(-50%)",
            color: C.textMuted,
            pointerEvents: "none",
          }}
        >
          {Ic.link()}
        </div>
        <input
          disabled={locked}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={onFocus}
          placeholder="https://github.com/org/repo"
          style={{
            ...inp(locked),
            paddingLeft: 32,
            borderColor: trimmed && !valid ? "#f59e0b" : undefined,
          }}
        />
      </div>

      {changesPrior && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#92400e" }}>
          {Ic.info(10)} Setting a new source will reset all downstream results.
        </div>
      )}

      {trimmed && !valid && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#b45309" }}>
          {Ic.info(10)} Enter a full http(s) URL.
        </div>
      )}

      {valid && !changesPrior && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            fontSize: 11,
            fontFamily: F.mono,
            color: "#16a34a",
          }}
        >
          {Ic.check(10)}
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {trimmed}
          </span>
        </div>
      )}
    </div>
  );
}
