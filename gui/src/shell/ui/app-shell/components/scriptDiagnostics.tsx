import type { LintFinding } from "@shell/data/scriptLint/findings";
import { createContext, type ReactNode, useContext } from "react";

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
