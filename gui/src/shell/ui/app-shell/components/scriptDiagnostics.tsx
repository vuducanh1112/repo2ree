import type { LintFinding } from "@shell/data/scriptLint/findings";
import { createContext, type ReactNode, useContext } from "react";

/** The channel from the analysis panel back up to the editor above it.
 *
 * `RunScriptCard` owns the editor; `ScriptAnalysis` owns the query that finds
 * out what is wrong with the script — and the pages in between compose the two
 * through the card's `renderAnalysis` prop, so the panel is not the card's own
 * child to pass props to. Rather than thread a callback through every page's
 * render prop, the card opens this channel and the panel publishes into it.
 *
 * The default is a no-op, so a panel rendered on its own (as its unit tests do)
 * simply has nowhere to publish. */
type PublishFindings = (findings: readonly LintFinding[]) => void;

const ScriptDiagnosticsContext = createContext<PublishFindings>(() => {});

interface ScriptDiagnosticsBridgeProps {
  publish: PublishFindings;
  children: ReactNode;
}

export function ScriptDiagnosticsBridge({ publish, children }: ScriptDiagnosticsBridgeProps) {
  return (
    <ScriptDiagnosticsContext.Provider value={publish}>
      {children}
    </ScriptDiagnosticsContext.Provider>
  );
}

export function usePublishScriptDiagnostics(): PublishFindings {
  return useContext(ScriptDiagnosticsContext);
}
