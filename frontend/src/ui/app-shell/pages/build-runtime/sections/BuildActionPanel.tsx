import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../../../application/workflow/WorkflowTypes";
import { S_SECTION_LABEL_MB12, S_WORKFLOW_BUILD_SECTION_WRAP } from "../../../../theme/theme";
import { RuntimeOutputNode, WorkflowRunActionSection } from "../../../components/workflowRunPanels";
import type { WorkflowPageProps } from "../../sharedWorkflowUi";

interface BuildActionPanelProps {
  buildColor: string;
  running: boolean;
  runDone: boolean;
  missing: WorkflowPageProps["missing"];
  onRun: WorkflowPageProps["onRun"];
  onCancel: WorkflowPageProps["onCancel"];
  workflowKey: AutomationStepKey;
  buildParams: AutomationStepRunParams<"build">;
  expectedOutput: string;
  ree: WorkflowPageProps["ree"];
  imageColor: string;
  files: WorkflowPageProps["workspaceFiles"];
}

export function BuildActionPanel({
  buildColor,
  running,
  runDone,
  missing,
  onRun,
  onCancel,
  workflowKey,
  buildParams,
  expectedOutput,
  ree,
  imageColor,
  files,
}: BuildActionPanelProps) {
  return (
    <>
      <WorkflowRunActionSection
        color={buildColor}
        running={running}
        runDone={runDone}
        disabled={running || missing.length > 0}
        idleLabel="Run build"
        runningLabel="Building…"
        doneLabel="Re-build"
        helperText="Execute the build script and record build logs."
        onCancel={() => onCancel?.(workflowKey)}
        onRun={() => onRun(workflowKey, buildParams)}
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
