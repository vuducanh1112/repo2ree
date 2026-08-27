import type { AppShellPage } from "@core/app-shell/pages";
import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import {
  type ActionStates,
  type Badges,
  isSuccessfulStepOutcome,
  type ReeRunLogs,
} from "@core/ree/ReeTypes";
import { isAuditCurrent } from "@core/ree/StepEvidence";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { ARCHIVE_REPOSITORIES } from "@core/ree-steps/archiveRepositories";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import { Badge } from "@shell/ui/shared/components/Badge";
import { Ic } from "@shell/ui/shared/components/Icon";
import { archiveTone } from "@shell/ui/theme/appearance";
import { useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import {
  GlassAside,
  GlassMainGrid,
  GlassPageShell,
  GlassPanel,
  GlassSectionBody,
} from "../../components/GlassPageShell";
import { GlassPanelFooter } from "../../components/GlassPanelFooter";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { ArchiveActionPanel } from "./sections/ArchiveActionPanel";
import { ArchiveParamsCard } from "./sections/ArchiveParamsCard";
import { ArchivePrereqBanners } from "./sections/ArchivePrereqBanners";
import { ArchiveReadinessAside } from "./sections/ArchiveReadinessAside";
import { ArchiveRepoSummaryCard } from "./sections/ArchiveRepoSummaryCard";
import { ArchiveRepoTabs } from "./sections/ArchiveRepoTabs";

interface PageArchiveProps {
  ree: ReeEditorViewModel;
  artifactStatus: ArtifactStatus;
  badges: Badges;
  logs: ReeRunLogs;
  actionStates: ActionStates;
  onRun: (key: string, params: GenericReeStepParams) => void;
  onGo: (key: AppShellPage) => void;
}

export function PageArchive({
  ree,
  artifactStatus,
  badges,
  logs,
  actionStates,
  onRun,
}: PageArchiveProps) {
  const [activeRepo, setActiveRepo] = useState("swh");
  const repo =
    ARCHIVE_REPOSITORIES.find((archiveRepo) => archiveRepo.key === activeRepo) ||
    ARCHIVE_REPOSITORIES[0];
  const earned = isSuccessfulStepOutcome(badges[activeRepo]);
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

  const requirementValues = { ...ree.spec, ...ree.source };
  const missing = repo.requires.filter((requiredField) => !requirementValues[requiredField.field]);
  const canRun = missing.length === 0 && !running;

  // Deposit identifiers are archive-binding attestations held server-side, not
  // fields on the REE. Undefined until the deposit API reads them back; the
  // cards below already render their placeholder in that state.
  const assignedId: string | undefined = undefined;

  const buildDone = isAuditCurrent(ree.audit, "runtime");
  const sbomDone = isAuditCurrent(ree.audit, "sbom");
  const activationDone = isAuditCurrent(ree.audit, "test_activation");
  const capstoneReady = buildDone && sbomDone && activationDone;
  const isSealed = !!artifactStatus.sealedAt;
  const depositedAnywhere = ["swh", "zenodo", "dataverse"].some((key) =>
    isSuccessfulStepOutcome(badges[key]),
  );

  return (
    <GlassPageShell variant="docked">
      <GlassPageHeader
        icon={Ic.globe(24)}
        tint={archiveTone(repo.key)}
        title="Deposit & Share"
        subtitle="Deposit your REE to a long-term archive and receive a citable permanent identifier."
        badges={
          <>
            <Badge tone={capstoneReady ? "success" : "warning"}>
              {capstoneReady ? "Prereqs ready" : "Prereqs pending"}
            </Badge>
            <Badge tone={depositedAnywhere ? "success" : "warning"}>
              {depositedAnywhere ? "Deposited" : "Not deposited"}
            </Badge>
            {assignedId && <Badge tone="success">{repo.idLabel} assigned</Badge>}
          </>
        }
      />

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

      <GlassMainGrid>
        <GlassPanel clipped>
          <GlassSectionBody>
            <GlassSectionHeader
              icon={Ic.archive(19)}
              tint={archiveTone(repo.key)}
              title={repo.label}
              subtitle="Review the destination and provide the parameters this archive requires."
            />

            <ArchiveRepoSummaryCard repo={repo} assignedId={assignedId} />
            <ArchiveParamsCard repo={repo} getParam={getParam} setParam={setParam} />
          </GlassSectionBody>

          <GlassPanelFooter>
            {isSealed
              ? "REE is sealed — deposits are final."
              : "Deposit can proceed before sealing, but Seal is still required to finish."}
          </GlassPanelFooter>
        </GlassPanel>

        <GlassAside>
          <ArchiveActionPanel
            repo={repo}
            canRun={canRun}
            earned={earned}
            running={running}
            missing={missing}
            logs={logs}
            onRun={onRun}
            getParam={getParam}
          />
          <ArchiveReadinessAside
            buildDone={buildDone}
            sbomDone={sbomDone}
            activationDone={activationDone}
            isSealed={isSealed}
            repo={repo}
            assignedId={assignedId}
          />
        </GlassAside>
      </GlassMainGrid>
    </GlassPageShell>
  );
}
