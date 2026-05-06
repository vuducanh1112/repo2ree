import type {
  ReeAssemblyOperationKey,
  ReeAssemblyRunParams,
} from "../../../../../core/ree-assembly/assemblyTypes";
import { S_SECTION_LABEL_MB12, S_WORKFLOW_BUILD_SECTION_WRAP } from "../../../../theme/theme";
import { AssemblyRunActionSection, RuntimeOutputNode } from "../../../components/assemblyRunPanels";
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
  expectedOutput: string;
  ree: AssemblyPageProps["ree"];
  imageColor: string;
  files: AssemblyPageProps["workspaceFiles"];
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
  expectedOutput,
  ree,
  imageColor,
  files,
}: BuildActionPanelProps) {
  return (
    <>
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

      <div style={S_WORKFLOW_BUILD_SECTION_WRAP}>
        <div style={S_SECTION_LABEL_MB12}>Step 3: Verify Build Output</div>
        <RuntimeOutputNode
          expectedOutput={expectedOutput}
          buildDone={runDone}
          ree={ree}
          imageColor={imageColor}
          files={files || []}
        />
      </div>
    </>
  );
}
