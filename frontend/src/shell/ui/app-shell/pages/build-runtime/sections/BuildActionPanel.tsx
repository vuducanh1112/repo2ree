import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../../../../core/ree-assembly/assemblyTypes";
import { AssemblyRunActionSection } from "../../../components/assemblyRunPanels";
import type { AssemblyPageProps } from "../../sharedAssemblyUi";

interface BuildActionPanelProps {
  buildColor: string;
  running: boolean;
  runDone: boolean;
  missing: AssemblyPageProps["missing"];
  onRun: AssemblyPageProps["onRun"];
  onCancel: AssemblyPageProps["onCancel"];
  assemblyKey: ReeAssemblyOperationKey;
  buildParams: ReeAssemblyRunParams<"build">;
}

export function BuildActionPanel({
  buildColor,
  running,
  runDone,
  missing,
  onRun,
  onCancel,
  assemblyKey,
  buildParams,
}: BuildActionPanelProps) {
  return (
    <AssemblyRunActionSection
      color={buildColor}
      running={running}
      runDone={runDone}
      disabled={running || missing.length > 0}
      idleLabel="Run build"
      runningLabel="Building…"
      doneLabel="Re-build"
      helperText="Execute the build script and record build logs."
      onCancel={() => onCancel?.(assemblyKey)}
      onRun={() => onRun(assemblyKey, buildParams)}
    />
  );
}
