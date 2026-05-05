import { useMemo, useState } from "react";
import { PAGE } from "../../../../application/state/pages";
import type { AutomationStepRunParams } from "../../../../application/workflow/WorkflowTypes";
import { Ic } from "../../../shared/components/Icon";
import {
  S_SECTION_LABEL,
  S_WORKFLOW_PAGE_BODY,
  S_WORKFLOW_PAGE_LOG_WRAP,
  S_WORKFLOW_PAGE_NUDGE_WRAP,
  S_WORKFLOW_PAGE_SCRIPTS_WRAP,
  S_WORKFLOW_SERVICE_MAIN_SCROLL,
  S_WORKFLOW_SERVICE_ROOT,
} from "../../../theme/theme";
import { descToTwoTierTips, FieldTipsSidebar } from "../../components/fieldTips";
import { NextStepNudge, WorkflowPageHeader } from "../../components/pageChrome";
import { ScriptPanel } from "../../components/scriptAndFile";
import { WorkflowLogSection, WorkflowRunActionSection } from "../../components/workflowRunPanels";
import { SVC_SCRIPT_FIELDS } from "../sharedWorkflowConstants";
import { findFileByPath } from "../sharedWorkflowHelpers";
import type { WorkflowPageProps } from "../sharedWorkflowUi";
import { goToBuild, SbomProducedSection, SbomRuntimeInputSection } from "./GenerateSbomSections";

const SBOM_PARSE_CHAR_LIMIT = 300_000;
const SBOM_PREVIEW_CHAR_LIMIT = 120_000;

export function PageGenerateSBOM({
  workflow,
  ree: reeDraft,
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
  onReeChange,
  onFilesChange,
  onPersistWorkspaceFile,
}: WorkflowPageProps) {
  const sbomParams: AutomationStepRunParams<"sbom"> = {
    ...(params as AutomationStepRunParams<"sbom">),
    produced_runtime_path: reeDraft.runtime,
  };

  const files = workspaceFiles;
  const sbomColor = workflow.color;
  const rt = reeDraft.runtime && reeDraft.runtime !== "__skipped__" ? reeDraft.runtime : null;
  const isTb = !!(rt && /\.(tar\.gz|tgz)$/i.test(rt));
  const hasSbom = !!(reeDraft.sbom && reeDraft.sbom !== "__skipped__");
  const sbomNode = hasSbom ? findFileByPath(files || [], reeDraft.sbom) : null;
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const sbomText = sbomNode?.content || "";
  const sbomUnavailable = !!sbomNode && !sbomNode.content && (sbomNode.size || 0) > 0;
  const sbomTooLargeForPreview = sbomText.length > SBOM_PREVIEW_CHAR_LIMIT;
  const sbomPreviewText = sbomTooLargeForPreview
    ? `${sbomText.slice(0, SBOM_PREVIEW_CHAR_LIMIT)}\n\n... preview truncated ...`
    : sbomText;

  const sbomScripts = SVC_SCRIPT_FIELDS[workflow.key] || [];
  const pkgCount = useMemo(() => {
    if (!hasSbom || !sbomNode?.content) return null;
    if (sbomNode.content.length > SBOM_PARSE_CHAR_LIMIT) return null;
    try {
      return JSON.parse(sbomNode.content)?.packages?.length ?? null;
    } catch {
      return null;
    }
  }, [hasSbom, sbomNode?.content]);

  return (
    <div style={S_WORKFLOW_SERVICE_ROOT}>
      <WorkflowPageHeader
        color={workflow.color}
        icon={Ic.package(18)}
        title="Generate SBOM"
        subtitle="Generate a machine-readable SBOM from the runtime image/tarball"
        tips={descToTwoTierTips(workflow.desc)}
        runDone={runDone}
        badge={badge}
        ts={ts}
        missingCount={missing.length}
        onGoFields={onGoFields}
      />

      <div style={S_WORKFLOW_PAGE_BODY}>
        <div style={S_WORKFLOW_SERVICE_MAIN_SCROLL}>
          <SbomRuntimeInputSection
            rt={rt}
            isTb={isTb}
            sbomColor={sbomColor}
            focusedField={focusedField}
            onFocusField={setFocusedField}
            onGoBuild={() => goToBuild(onGo as (key: typeof PAGE.BUILD) => void)}
          />

          <WorkflowRunActionSection
            color={sbomColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Generate SBOM"
            runningLabel="Generating…"
            doneLabel="Regenerate SBOM"
            helperText="Generate an SPDX JSON SBOM from the selected runtime."
            onCancel={() => onCancel?.(workflow.key)}
            onRun={() => onRun(workflow.key, sbomParams)}
          />

          <SbomProducedSection
            sbomColor={sbomColor}
            hasSbom={hasSbom}
            sbomNode={sbomNode}
            sbomUnavailable={sbomUnavailable}
            sbomTooLargeForPreview={sbomTooLargeForPreview}
            sbomPreviewText={sbomPreviewText}
            pkgCount={pkgCount}
            reeDraft={reeDraft}
            focusedField={focusedField}
            onFocusField={setFocusedField}
          />

          {sbomScripts.length > 0 && (
            <div style={S_WORKFLOW_PAGE_SCRIPTS_WRAP}>
              <div style={{ ...S_SECTION_LABEL, marginBottom: 14 }}>Scripts</div>
              {sbomScripts.map((sf) => (
                <ScriptPanel
                  key={sf.fieldKey}
                  scriptKind={sf.scriptKind || null}
                  fieldKey={sf.fieldKey}
                  files={files || []}
                  onFilesChange={onFilesChange}
                  onPersistWorkspaceFile={onPersistWorkspaceFile}
                  ree={reeDraft}
                  onReeChange={onReeChange}
                />
              ))}
            </div>
          )}

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <WorkflowLogSection log={log} running={running} />
          </div>

          <div style={S_WORKFLOW_PAGE_NUDGE_WRAP}>
            <NextStepNudge stepKey={PAGE.SBOM} badges={badges || {}} onGo={onGo || (() => {})} />
          </div>
        </div>

        <FieldTipsSidebar
          tipFields={["runtime", "sbom"]}
          focusedField={focusedField}
          onFocusField={setFocusedField}
          onClear={() => setFocusedField(null)}
          emptyMessage="Choose a field to see examples, format rules, and commands."
        />
      </div>
    </div>
  );
}
