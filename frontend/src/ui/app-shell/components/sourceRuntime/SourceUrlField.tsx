import { useRef, useState } from "react";
import { Ic } from "../../../shared/components/Icon";
import { C, F, hoverBrightness, hoverIf, S_SOURCE_URL_STATUS_BASE } from "../../../theme/theme";
import { inp } from "./shared";

interface SourceUrlFieldProps {
  locked: boolean;
  committedValue: string;
  onCommit: (value: string) => void;
  onFocus?: () => void;
}
export function SourceUrlField({ locked, committedValue, onCommit, onFocus }: SourceUrlFieldProps) {
  const [draft, setDraft] = useState(committedValue || "");
  const [checkState, setCheckState] = useState<"idle" | "checking" | "reachable" | "unreachable">(
    "idle",
  );
  const [checkedFor, setCheckedFor] = useState<string>("");

  const prevCommitted = useRef<string | undefined>(committedValue);
  if (prevCommitted.current !== committedValue) {
    prevCommitted.current = committedValue;
    setDraft(committedValue || "");
    if ((committedValue || "") !== checkedFor) {
      setCheckState("idle");
      setCheckedFor("");
    }
  }

  const isDirty = draft.trim() !== (committedValue || "").trim();

  const handleCheckReachable = async () => {
    const candidate = draft.trim();
    if (!candidate) return;
    setCheckState("checking");
    setCheckedFor(candidate);
    await new Promise((resolve) => setTimeout(resolve, 700));
    const reachable = /^https?:\/\/[^\s]+$/i.test(candidate);
    setCheckState(reachable ? "reachable" : "unreachable");
    if (reachable) onCommit(candidate);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "stretch",
        }}
      >
        <div
          style={{
            flex: 1,
            position: "relative",
          }}
        >
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
            value={draft}
            onChange={(event) => {
              const next = event.target.value;
              setDraft(next);
              if (!next.trim()) {
                onCommit("");
              }
              if (checkedFor && next.trim() !== checkedFor) {
                setCheckState("idle");
                setCheckedFor("");
              }
            }}
            onFocus={onFocus}
            onKeyDown={(event) => {
              if (event.key === "Enter" && draft.trim()) handleCheckReachable();
            }}
            placeholder="https://github.com/org/repo"
            style={{
              ...inp(locked),
              paddingLeft: 32,
              borderColor: isDirty ? "#f59e0b" : undefined,
            }}
          />
        </div>
        <button
          type="button"
          onClick={handleCheckReachable}
          disabled={locked || !draft.trim() || checkState === "checking"}
          style={{
            ...{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "7px 13px",
              borderRadius: 7,
              fontSize: 13,
              fontWeight: 600,
              fontFamily: F.sans,
              flexShrink: 0,
              transition: "all 0.15s",
              whiteSpace: "nowrap",
            },
            cursor: locked || !draft.trim() || checkState === "checking" ? "default" : "pointer",
            border: `1.5px solid ${draft.trim() ? C.accentBorder : C.border}`,
            background: draft.trim() ? C.accentBg : C.surfaceAlt,
            color: draft.trim() ? C.accent : C.textMuted,
            opacity: locked ? 0.5 : 1,
          }}
          {...hoverIf(!locked && !!draft.trim() && checkState !== "checking", hoverBrightness(96))}
        >
          {checkState === "checking" ? Ic.loader(13) : Ic.link(13)} Check reachable
        </button>
      </div>
      {isDirty && draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#92400e" }}>
          {Ic.info(10)} Setting a new source will reset all downstream results.
        </div>
      )}
      {committedValue && !isDirty && (
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
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {committedValue}
          </span>
        </div>
      )}
      {checkState === "reachable" && checkedFor === draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#15803d" }}>
          {Ic.check(10)} URL reachable
        </div>
      )}
      {checkState === "unreachable" && checkedFor === draft.trim() && (
        <div style={{ ...S_SOURCE_URL_STATUS_BASE, color: "#b45309" }}>
          {Ic.info(10)} URL not reachable (or invalid format)
        </div>
      )}
    </div>
  );
}
