import { useState } from "react";
import { type AppShellPage, PAGE } from "../../../../application/state/pages";
import { ARCHIVE_REPOSITORIES } from "../../../../application/workflow/archiveRepositories";
import type { GenericWorkflowParams } from "../../../../application/workflow/WorkflowStepTypes";
import type { ArtifactStatus } from "../../../../domain/artifact/ArtifactStatus";
import type { ActionStates, Badges, WorkflowLogs } from "../../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../../domain/ree/ReeViewState";
import { Ic } from "../../../shared/components/Icon";
import { S_FIELD_STACK_GAP_14 } from "../../../theme/theme";
import { NextStepNudge, RequirementsBanner, WorkflowPageHeader } from "../../components/pageChrome";
import { ArchiveActionPanel } from "./sections/ArchiveActionPanel";
import { ArchiveParamsCard } from "./sections/ArchiveParamsCard";
import { ArchivePrereqBanners } from "./sections/ArchivePrereqBanners";
import { ArchiveRepoSummaryCard } from "./sections/ArchiveRepoSummaryCard";
import { ArchiveRepoTabs } from "./sections/ArchiveRepoTabs";

interface PageArchiveProps {
  ree: ReeViewState;
  artifactStatus: ArtifactStatus;
  badges: Badges;
  logs: WorkflowLogs;
  actionStates: ActionStates;
  onRun: (key: string, params: GenericWorkflowParams) => void;
  onGo: (key: AppShellPage) => void;
}

export function PageArchive({
  ree,
  artifactStatus,
  badges,
  logs,
  actionStates,
  onRun,
  onGo,
}: PageArchiveProps) {
  const [activeRepo, setActiveRepo] = useState("swh");
  const repo =
    ARCHIVE_REPOSITORIES.find((archiveRepo) => archiveRepo.key === activeRepo) ||
    ARCHIVE_REPOSITORIES[0];
  const earned = !!badges[activeRepo];
  const running = actionStates[activeRepo] === "loading";
  const [params, setParams] = useState<Record<string, string | boolean>>(() =>
    Object.fromEntries(
      ARCHIVE_REPOSITORIES.flatMap((archiveRepo) =>
        archiveRepo.params.map((param) => [`${archiveRepo.key}_${param.key}`, param.default]),
      ),
    ),
  );

  const getParam = (repoKey: string, paramKey: string): string | boolean =>
    params[`${repoKey}_${paramKey}`];

  const setParam = (repoKey: string, paramKey: string, val: string | boolean) =>
    setParams((prevParams) => ({ ...prevParams, [`${repoKey}_${paramKey}`]: val }));

  const missing = repo.requires.filter((requiredField) => !ree[requiredField.field]);
  const canRun = missing.length === 0 && !running;

  const assignedId = ree[repo.idField] as string | undefined;

  const buildDone = !!badges.build;
  const sbomDone = !!badges.sbom;
  const activationDone = !!badges.activation;
  const capstoneReady = buildDone && sbomDone && activationDone;
  const isSealed = !!artifactStatus.sealedAt;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
        overflow: "hidden",
        animation: "fadeUp 0.2s ease",
      }}
    >
      <WorkflowPageHeader
        color={repo.color}
        icon={Ic.globe(18)}
        title="Deposit & Share"
        subtitle="Deposit your REE to a long-term archive and receive a citable permanent identifier"
        tips={[
          "Complete Build Runtime, SBOM, and Activation before depositing.",
          "Choose one repository and provide the parameters required by that archive.",
        ]}
      />

      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        <div style={{ padding: 24, maxWidth: 860 }}>
          <ArchivePrereqBanners
            capstoneReady={capstoneReady}
            buildDone={buildDone}
            sbomDone={sbomDone}
            activationDone={activationDone}
            isSealed={isSealed}
          />

          <ArchiveRepoTabs
            repositories={ARCHIVE_REPOSITORIES}
            activeRepo={activeRepo}
            badges={badges}
            onSelect={setActiveRepo}
          />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={S_FIELD_STACK_GAP_14}>
              <ArchiveRepoSummaryCard repo={repo} assignedId={assignedId} />
              <ArchiveParamsCard repo={repo} getParam={getParam} setParam={setParam} />
              {missing.length > 0 && <RequirementsBanner status="missing" items={missing} />}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <ArchiveActionPanel
                repo={repo}
                canRun={canRun}
                earned={earned}
                running={running}
                logs={logs}
                onRun={onRun}
                getParam={getParam}
              />
            </div>
          </div>

          <div style={{ padding: "24px 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={PAGE.ARCHIVE} badges={badges || {}} onGo={onGo} />
          </div>
        </div>
      </div>
    </div>
  );
}
