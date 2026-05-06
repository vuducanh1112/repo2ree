import { useMemo, useState } from "react";
import type { ReeAssemblyRunParams } from "../../../../../core/ree-assembly/assemblyTypes";
import { Ic } from "../../../shared/components/Icon";
import {
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import { AssemblyRunLogSection } from "../../components/assemblyRunPanels";
import { descToTwoTierTips, FieldTipsSidebar } from "../../components/fieldTips";
import { AssemblyPageHeader, NextStepNudge } from "../../components/pageChrome";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { deriveRuntimeFileSize } from "./buildRuntimeHelpers";
import { BuildActionPanel } from "./sections/BuildActionPanel";
import { BuildScriptSection } from "./sections/BuildScriptSection";
import { ExpectedOutputSection } from "./sections/ExpectedOutputSection";
import { FinalRuntimeSection } from "./sections/FinalRuntimeSection";
import { ManualOverridePanel } from "./sections/ManualOverridePanel";

export function PageBuildRuntime({
  assemblyStep,
  ree,
  inclusionState,
  badges,
  workspaceFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onCancel,
  onGo,
  onGoFields,
  missing,
  params,
  setParam,
  onReeSpecChange,
  onArtifactStatusChange,
  onPersistWorkspaceFile,
}: AssemblyPageProps) {
  const files = workspaceFiles;

  const [expectedOutput, setExpectedOutput] = useState(() =>
    ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "",
  );
  const buildParams: ReeAssemblyRunParams<"build"> = {
    ...(params as ReeAssemblyRunParams<"build">),
    build_runtime_script_path: ree.build_runtime_script,
    produced_runtime_path: expectedOutput,
    _expectedOutput: expectedOutput,
  };
  const [showManualOverride, setShowManualOverride] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const buildColor = assemblyStep.color;
  const imageColor = "#0891b2";
  const finalRuntime = ree.runtime && ree.runtime !== "__skipped__" ? ree.runtime : "";
  const includeRuntime = inclusionState.runtime === "included";
  const finalRuntimeFile = useMemo(() => {
    if (!finalRuntime) return null;
    return (
      findFileByPath(files || [], finalRuntime) ||
      findFileByPath(files || [], finalRuntime.split("/").pop() || "")
    );
  }, [files, finalRuntime]);
  const finalRuntimeSize = useMemo(
    () => deriveRuntimeFileSize(finalRuntimeFile),
    [finalRuntimeFile],
  );

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <AssemblyPageHeader
        color={assemblyStep.color}
        icon={Ic.cpu(18)}
        title={assemblyStep.label}
        subtitle={assemblyStep.desc}
        tips={descToTwoTierTips(assemblyStep.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        timestampPrefix="Last built"
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          <BuildScriptSection
            assemblyStep={assemblyStep}
            ree={ree}
            files={files}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
            onReeSpecChange={onReeSpecChange}
            onPersistWorkspaceFile={onPersistWorkspaceFile}
            onTemplateSuggestedOutput={setExpectedOutput}
          />

          <ExpectedOutputSection
            assemblyStep={assemblyStep}
            expectedOutput={expectedOutput}
            setExpectedOutput={setExpectedOutput}
            params={params}
            setParam={setParam}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
          />

          <BuildActionPanel
            buildColor={buildColor}
            running={running}
            runDone={runDone}
            missing={missing}
            onRun={onRun}
            onCancel={onCancel}
            assemblyKey={assemblyStep.key}
            buildParams={buildParams}
            expectedOutput={expectedOutput}
            ree={ree}
            imageColor={imageColor}
            files={files}
          />

          <ManualOverridePanel
            showManualOverride={showManualOverride}
            onToggleManualOverride={setShowManualOverride}
            ree={ree}
            onReeSpecChange={onReeSpecChange}
            files={files}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
          />

          <FinalRuntimeSection
            includeRuntime={includeRuntime}
            finalRuntime={finalRuntime}
            finalRuntimeSize={finalRuntimeSize}
            onArtifactStatusChange={onArtifactStatusChange}
            focusedField={focusedField}
            setFocusedField={setFocusedField}
          />

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <AssemblyRunLogSection log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge
              stepKey={assemblyStep.key}
              badges={badges || {}}
              onGo={onGo || (() => {})}
            />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["build_runtime_script", "runtime"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
        />
      </div>
    </div>
  );
}
