import type React from "react";
import type { LogEntry } from "../../../../domain/ree/ReeTypes";
import { C, S_SECTION_LABEL } from "../../../theme/theme";
import { LogPanel } from "../logPanel";
import { workflowSectionCardStyle } from "../statusUiStyles";

interface WorkflowLogSectionProps {
  log: LogEntry | null;
  running: boolean;
  title?: string;
  titleStyle?: React.CSSProperties;
}
export function WorkflowLogSection({
  log,
  running,
  title = "Output",
  titleStyle,
}: WorkflowLogSectionProps) {
  return (
    <div style={workflowSectionCardStyle(false)}>
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
