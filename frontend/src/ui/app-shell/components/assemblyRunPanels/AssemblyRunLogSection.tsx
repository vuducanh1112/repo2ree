import type React from "react";
import type { LogEntry } from "../../../../core/ree/ReeTypes";
import { C, S_SECTION_LABEL } from "../../../theme/theme";
import { LogPanel } from "../logPanel";
import { assemblySectionCardStyle } from "../statusUiStyles";

interface AssemblyRunLogSectionProps {
  log: LogEntry | null;
  running: boolean;
  title?: string;
  titleStyle?: React.CSSProperties;
}
export function AssemblyRunLogSection({
  log,
  running,
  title = "Output",
  titleStyle,
}: AssemblyRunLogSectionProps) {
  return (
    <div style={assemblySectionCardStyle(false)}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ ...S_SECTION_LABEL, marginBottom: 0, ...titleStyle }}>{title}</div>
        <div style={{ fontSize: 12, color: C.textMuted }}>
          {running ? "Streaming" : "Latest run"}
        </div>
      </div>
      <LogPanel log={log} running={running} />
    </div>
  );
}
