import { DEFAULT_REE_ID } from "../../../../../core/ree/ReeId";
import type { SourceUploadCommit } from "../../../../../core/ree/ReeTypes";
import { useApiRuntime } from "../../../../data/apiRuntime";
import { useAssemblyStepPageController } from "../../hooks/useAssemblyStepPageController";
import { PAGE } from "../../state/pages";
import {
  type AssemblyPageProps,
  PageBuildRuntime,
  PageEvaluate,
  PageExperiments,
  PageGenerateSBOM,
  PageHardwareBom,
  PageMetadataEntry,
  PageTestActivation,
  SourceAcquisitionPage,
  WorkbenchPage,
} from "../index";
import { type AppShellPageContainerProps, ContentSection, useAssemblyRunLogEntry } from "./shared";

export function WorkbenchPageContainer({ ree, uiChrome }: AppShellPageContainerProps) {
  const { reeId, reeApi } = useApiRuntime();
  const { page } = uiChrome;

  if (page !== PAGE.WORKBENCH) {
    return null;
  }

  const provisioned = reeId !== DEFAULT_REE_ID;

  return (
    <ContentSection>
      <WorkbenchPage provisioned={provisioned} reeId={reeId} reeApi={reeApi} reeName={ree.name} />
    </ContentSection>
  );
}

const ASSEMBLY_PAGE_COMPONENTS: Record<string, (props: AssemblyPageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSBOM {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

export function SourcePageContainer({
  ree,
  workspaceRemote,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField, locked, repoMode } = uiChrome;
  const { badges, actionStates } = assemblyRun;
  const sourceLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.source,
    fallbackTimestamp: assemblyRun.timestamps.source,
  });

  if (page !== PAGE.SOURCE) {
    return null;
  }

  return (
    <SourceAcquisitionPage
      ree={ree}
      workspaceSourceState={workspaceRemote.workspaceSourceState}
      locked={locked}
      repoMode={repoMode}
      badges={badges}
      actionStates={actionStates}
      log={sourceLog}
      running={actionStates.source === "loading"}
      focusedField={focusedField}
      onWorkspaceSourceStateChange={commands.setWorkspaceSourceState}
      onRepoModeChange={commands.setRepoMode}
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onDownloadSource={commands.onDownloadSourceFiles}
      onCancelSource={() => commands.onCancelAction("source")}
      onWorkspaceUpload={(payload: SourceUploadCommit) => commands.onWorkspaceUpload(payload)}
      onRemoveWorkspaceSource={commands.onRemoveWorkspaceSource}
    />
  );
}

export function MetadataPageContainer({
  reeIntent,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { page, focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const { badges } = assemblyRun;

  if (page !== PAGE.METADATA) {
    return null;
  }

  return (
    <PageMetadataEntry
      reeSpec={reeSpec}
      locked={locked}
      badges={badges}
      focusedField={focusedField}
      onReeChange={commands.setReeSpec}
      onLockedChange={commands.setLocked}
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
    />
  );
}

export function ExperimentsPageContainer({
  reeIntent,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId, reeApi } = useApiRuntime();
  const { page, focusedField, locked } = uiChrome;
  const { reeSpec } = reeIntent;
  const { badges } = assemblyRun;

  if (page !== PAGE.EXPERIMENTS) {
    return null;
  }

  async function handleSnapshotComplete() {
    const fresh = await reeApi.getRee(reeId);
    const freshExperiments = (fresh.reeIntent as { experiments?: unknown[] }).experiments ?? [];
    commands.setReeSpec((prev) => ({
      ...prev,
      experiments: freshExperiments as typeof prev.experiments,
    }));
  }

  return (
    <PageExperiments
      reeId={reeId}
      reeSpec={reeSpec}
      locked={locked}
      badges={badges}
      focusedField={focusedField}
      onReeChange={commands.setReeSpec}
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onSnapshotComplete={handleSnapshotComplete}
      onBeforeRun={commands.flushReeIntent}
    />
  );
}

export function HardwareBomPageContainer({
  ree,
  assemblyRun,
  uiChrome,
  commands,
}: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page, focusedField, locked } = uiChrome;
  const { badges, actionStates, timestamps } = assemblyRun;
  const hbomLog = useAssemblyRunLogEntry({
    reeId,
    runId: assemblyRun.activeRunIds.hbom,
    fallbackTimestamp: timestamps.hbom,
  });

  if (page !== PAGE.HBOM) {
    return null;
  }

  return (
    <PageHardwareBom
      ree={ree}
      locked={locked}
      badges={badges}
      log={hbomLog}
      running={actionStates.hbom === "loading"}
      runDone={!!badges.hbom}
      ts={timestamps.hbom}
      focusedField={focusedField}
      onReeSpecChange={commands.setReeSpec}
      onLockedChange={commands.setLocked}
      onGoAssemblyPage={commands.setPage}
      onFocusedFieldChange={commands.setFocusedField}
      onRun={commands.onRunAssemblyStep}
      onCancel={commands.onCancelAction}
    />
  );
}

export function AssemblyPageContainer(props: AppShellPageContainerProps) {
  const { ree, workspaceRemote, assemblyRun, commands } = props;
  const { badges } = assemblyRun;
  const { workspaceFiles, workspaceSourceState, artifactStatus } = workspaceRemote;

  const assemblyPageController = useAssemblyStepPageController(props);

  if (!assemblyPageController) {
    return null;
  }

  const {
    assemblyStep,
    log,
    running,
    runDone,
    badge,
    ts,
    missing,
    params,
    setParam,
    goToRequirements,
  } = assemblyPageController;

  const AssemblyPageComponent = ASSEMBLY_PAGE_COMPONENTS[assemblyStep.key];
  if (!AssemblyPageComponent) {
    return null;
  }

  return (
    <ContentSection>
      <AssemblyPageComponent
        assemblyStep={assemblyStep}
        ree={ree}
        badges={badges}
        workspaceFiles={workspaceFiles}
        workspaceSourceState={workspaceSourceState}
        artifactStatus={artifactStatus}
        evaluationState={assemblyRun.evaluationState}
        log={log}
        running={running}
        runDone={runDone}
        badge={badge}
        ts={ts}
        onRun={commands.onRunAssemblyStep}
        onCancel={commands.onCancelAction}
        onGo={commands.setPage}
        onGoFields={goToRequirements}
        onReeSpecChange={commands.setReeSpec}
        onArtifactStatusChange={commands.setArtifactStatus}
        onWorkspaceSourceStateChange={commands.setWorkspaceSourceState}
        onEvaluationStateChange={commands.setEvaluationState}
        onPersistWorkspaceFile={commands.onPersistWorkspaceFile}
        missing={missing}
        params={params}
        setParam={setParam}
      />
    </ContentSection>
  );
}
