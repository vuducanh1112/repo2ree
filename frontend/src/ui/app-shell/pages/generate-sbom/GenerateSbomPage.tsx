import { useMemo, useState } from "react";
import type { ReeAssemblyRunParams } from "../../../../core/ree-assembly/assemblyTypes";
import { PAGE } from "../../../../shell/ui/app-shell/state/pages";
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
import {
  AssemblyRunActionSection,
  AssemblyRunLogSection,
} from "../../components/assemblyRunPanels";
import { descToTwoTierTips, FieldTipsSidebar } from "../../components/fieldTips";
import { AssemblyPageHeader, NextStepNudge } from "../../components/pageChrome";
import { ScriptPanel } from "../../components/scriptAndFile";
import { SVC_SCRIPT_FIELDS } from "../sharedAssemblyConstants";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { goToBuild, SbomProducedSection, SbomRuntimeInputSection } from "./GenerateSbomSections";

const SBOM_PARSE_CHAR_LIMIT = 300_000;
const SBOM_PREVIEW_CHAR_LIMIT = 120_000;

export function PageGenerateSBOM({
  assemblyStep,
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
  onReeSpecChange,
  onPersistWorkspaceFile,
}: AssemblyPageProps) {
  const sbomParams: ReeAssemblyRunParams<"sbom"> = {
    ...(params as ReeAssemblyRunParams<"sbom">),
    produced_runtime_path: reeDraft.runtime,
  };

  const files = workspaceFiles;
  const sbomColor = assemblyStep.color;
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

  const sbomScripts = SVC_SCRIPT_FIELDS[assemblyStep.key] || [];
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
      <AssemblyPageHeader
        color={assemblyStep.color}
        icon={Ic.package(18)}
        title="Generate SBOM"
        subtitle="Generate a machine-readable SBOM from the runtime image/tarball"
        tips={descToTwoTierTips(assemblyStep.desc)}
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

          <AssemblyRunActionSection
            color={sbomColor}
            running={running}
            runDone={runDone}
            disabled={running || missing?.length > 0}
            idleLabel="Generate SBOM"
            runningLabel="Generating…"
            doneLabel="Regenerate SBOM"
            helperText="Generate an SPDX JSON SBOM from the selected runtime."
            onCancel={() => onCancel?.(assemblyStep.key)}
            onRun={() => onRun(assemblyStep.key, sbomParams)}
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
                  onPersistWorkspaceFile={onPersistWorkspaceFile}
                  ree={reeDraft}
                  onReeSpecChange={onReeSpecChange}
                />
              ))}
            </div>
          )}

          <div style={S_WORKFLOW_PAGE_LOG_WRAP}>
            <AssemblyRunLogSection log={log} running={running} />
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
