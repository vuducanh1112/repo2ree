import { type AppShellPage, PAGE } from "@core/app-shell/pages";
import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { ActionStates, Badges, ReeRunLogs } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { ARCHIVE_REPOSITORIES } from "@core/ree-steps/archiveRepositories";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import { Ic } from "@shell/ui/shared/components/Icon";
import { archiveTone, translucent } from "@shell/ui/theme/appearance";
import { lgColors, lgNextButton, lgStatusBadge, lgStyles } from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useState } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
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

  // Deposit identifiers are archive-binding attestations held server-side, not
  // fields on the REE. Undefined until the deposit API reads them back; the
  // cards below already render their placeholder in that state.
  const assignedId: string | undefined = undefined;

  const buildDone = !!badges.build;
  const sbomDone = !!badges.sbom;
  const activationDone = !!badges.activation;
  const capstoneReady = buildDone && sbomDone && activationDone;
  const isSealed = !!artifactStatus.sealedAt;
  const depositedAnywhere = !!badges.swh || !!badges.zenodo || !!badges.dataverse;

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <GlassPageHeader
          icon={Ic.globe(24)}
          iconTint={{
            color: archiveTone(repo.key),
            border: translucent(archiveTone(repo.key), 33),
            shadow: translucent(archiveTone(repo.key), 19),
          }}
          title="Deposit & Share"
          subtitle="Deposit your REE to a long-term archive and receive a citable permanent identifier."
          badges={
            <>
              <span style={lgStatusBadge(capstoneReady)}>
                {capstoneReady ? "Prereqs ready" : "Prereqs pending"}
              </span>
              <span style={lgStatusBadge(depositedAnywhere)}>
                {depositedAnywhere ? "Deposited" : "Not deposited"}
              </span>
              {assignedId && <span style={lgStatusBadge(true)}>{repo.idLabel} assigned</span>}
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

        <div style={lgStyles.mainGrid}>
          <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
            <div style={lgStyles.sectionBody}>
              <GlassSectionHeader
                icon={Ic.archive(19)}
                color={archiveTone(repo.key)}
                title={repo.label}
                subtitle="Review the destination and provide the parameters this archive requires."
              />

              <ArchiveRepoSummaryCard repo={repo} assignedId={assignedId} />
              <ArchiveParamsCard repo={repo} getParam={getParam} setParam={setParam} />
            </div>

            <div style={lgStyles.footer}>
              <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
                {isSealed
                  ? "REE is sealed — deposits are final."
                  : "Deposit can proceed before sealing, but Seal is still required to finish."}
              </span>
              <button type="button" onClick={() => onGo(PAGE.SEAL)} style={lgNextButton()}>
                Next: Seal {Ic.chevR(15)}
              </button>
            </div>
          </section>

          <aside style={lgStyles.aside}>
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
          </aside>
        </div>
      </div>
    </div>
  );
}
