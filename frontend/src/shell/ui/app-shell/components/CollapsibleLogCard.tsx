import { useEffect, useState } from "react";
import type { LogEntry } from "../../../../core/ree/ReeTypes";
import { Ic } from "../../shared/components/Icon";
import { lgColors, lgContentCard, lgStyles } from "../../theme/lightGlassTheme";
import { LogPanel } from "./logPanel";

interface CollapsibleLogCardProps {
  log: LogEntry | null;
  running: boolean;
  title: string;
  maxHeight?: number;
}

export function CollapsibleLogCard({ log, running, title, maxHeight }: CollapsibleLogCardProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (running) setOpen(true);
  }, [running]);

  const show = running || open;
  const hint = running ? "Streaming" : log ? "Latest run" : "No runs yet";

  return (
    <div style={lgContentCard()}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 0,
          gap: 8,
        }}
      >
        <span
          style={{
            ...lgStyles.label,
            gap: 8,
            color: running ? lgColors.blue : lgColors.text,
          }}
        >
          {running && (
            <span style={{ display: "flex", color: lgColors.blue }}>{Ic.loader(14)}</span>
          )}
          {title}
          <span style={{ color: lgColors.textMuted, fontSize: 11, fontWeight: 400 }}>{hint}</span>
        </span>
        <span style={{ color: lgColors.textMuted, display: "flex" }}>
          {show ? Ic.chevD(14) : Ic.chevR(14)}
        </span>
      </button>
      {show && (
        <div
          style={{
            marginTop: 10,
            ...(maxHeight
              ? {
                  maxHeight,
                  overflow: "auto",
                  borderRadius: 8,
                  border: "1px solid rgba(125, 211, 252, 0.36)",
                  background: "rgba(15, 23, 42, 0.04)",
                }
              : null),
          }}
        >
          <LogPanel log={log} running={running} />
        </div>
      )}
    </div>
  );
}
