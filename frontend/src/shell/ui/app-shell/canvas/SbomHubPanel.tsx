import type { ReeAssemblyRunParams } from "@core/ree-assembly/assemblyTypes";
import { resolvedRuntimePath } from "@core/ree-assembly/buildRuntimeUiState";
import {
  isRuntimeTarballPath,
  resolvedSbomPath,
  summarizeSbom,
} from "@core/ree-assembly/sbomUiState";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { useMemo } from "react";
import { Ic } from "../../shared/components/Icon";
import {
  lgAccentActionButton,
  lgColors,
  lgInfoBanner,
  lgOutcomeBadge,
  lgStatusBadge,
} from "../../theme/lightGlassTheme";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import { MissingInputsBanner } from "../components/MissingInputsBanner";
import { RunActionButton } from "../components/RunActionButton";
import { useAssemblyStepPageController } from "../hooks/useAssemblyStepPageController";
import { RuntimeScanTargetCard, SbomOutputCard } from "../pages/generate-sbom/sections";
import type { AppShellPageContainerProps } from "../pages/pageContainers/shared";
import { findFileByPath } from "../pages/sharedAssemblyHelpers";
import { HubPanel, HubPanelHeader } from "./HubPanel";

const SBOM_PAGE_COLOR = "#16a34a";

type SbomHubPanelProps = Pick<
  AppShellPageContainerProps,
  "ree" | "workspaceRemote" | "assemblyRun" | "uiChrome" | "commands"
> & {
  onClose: () => void;
};

// SBOM is essentially a one-press action, so it opens as a compact floating
// panel in the hub — like the seal — rather than docking a full-size page.
export function SbomHubPanel({
  ree,
  workspaceRemote,
  assemblyRun,
  uiChrome,
  commands,
  onClose,
}: SbomHubPanelProps) {
  const controller = useAssemblyStepPageController({ ree, assemblyRun, uiChrome, commands });

  const files = workspaceRemote.workspaceFiles || [];
  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeIsTarball = !!runtimePath && isRuntimeTarballPath(runtimePath);

  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomNode = sbomPath ? findFileByPath(files, sbomPath) : null;
  const sbomSummary = useMemo(() => summarizeSbom(sbomNode), [sbomNode]);

  return (
    <HubPanel ariaLabel="Generate SBOM" onClose={onClose} width={460}>
      <HubPanelHeader
        icon={Ic.package(18)}
        iconColor={SBOM_PAGE_COLOR}
        title="Generate SBOM"
        subtitle="scan the runtime into a software inventory"
        right={
          controller && (
            <RunActionButton
              label={
                controller.running ? "Generating…" : controller.runDone ? "Regenerate" : "Generate"
              }
              running={controller.running}
              disabled={controller.running || controller.missing.length > 0 || !runtimePathExists}
              iconSize={13}
              style={lgAccentActionButton(
                SBOM_PAGE_COLOR,
                controller.running || controller.missing.length > 0 || !runtimePathExists,
              )}
              onRun={() =>
                commands.onRunAssemblyStep(controller.assemblyStep.key, {
                  ...(controller.params as ReeAssemblyRunParams<"sbom">),
                  produced_runtime_path: runtimePath,
                })
              }
              onCancel={() => commands.onCancelAction(controller.assemblyStep.key)}
            />
          )
        }
      />

      {!controller ? (
        <div style={{ fontSize: 12, color: lgColors.textMuted }}>SBOM step unavailable.</div>
      ) : (
        <SbomHubBody
          controller={controller}
          runtimePath={runtimePath}
          runtimePathExists={runtimePathExists}
          runtimeIsTarball={runtimeIsTarball}
          sbomPath={sbomPath}
          sbomFilePresent={!!sbomNode}
          pkgCount={sbomSummary.pkgCount}
          sbomFormat={sbomSummary.format}
          onGoFields={controller.goToRequirements}
        />
      )}
    </HubPanel>
  );
}

type Controller = NonNullable<ReturnType<typeof useAssemblyStepPageController>>;

function SbomHubBody({
  controller,
  runtimePath,
  runtimePathExists,
  runtimeIsTarball,
  sbomPath,
  sbomFilePresent,
  pkgCount,
  sbomFormat,
  onGoFields,
}: {
  controller: Controller;
  runtimePath: string;
  runtimePathExists: boolean;
  runtimeIsTarball: boolean;
  sbomPath: string;
  sbomFilePresent: boolean;
  pkgCount: number | null;
  sbomFormat: string | null;
  onGoFields: () => void;
}) {
  const { log, running, runDone, badge, ts, missing } = controller;

  const buildReady = !!runtimePath && runtimePathExists;
  const sbomReady = !!sbomPath && sbomFilePresent;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <span style={lgStatusBadge(buildReady)}>
          {buildReady ? "Build ready" : "Build pending"}
        </span>
        <span style={lgStatusBadge(sbomReady)}>{sbomReady ? "SBOM ready" : "SBOM pending"}</span>
        {runDone && badge && (
          <span style={lgOutcomeBadge(badge.color, badge.bg)}>
            {Ic.check(11)} {badge.label}
          </span>
        )}
      </div>

      <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

      {runtimePath && !runtimePathExists && (
        <div style={lgInfoBanner("danger")}>
          <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
          <span style={{ fontSize: 12, color: lgColors.danger }}>
            Runtime file must exist before SBOM generation can run.
          </span>
        </div>
      )}

      <RuntimeScanTargetCard
        runtimePath={runtimePath}
        runtimePathExists={runtimePathExists}
        runtimeIsTarball={runtimeIsTarball}
        color={SBOM_PAGE_COLOR}
      />

      <SbomOutputCard
        color={SBOM_PAGE_COLOR}
        sbomPath={sbomPath}
        sbomFilePresent={sbomFilePresent}
        pkgCount={pkgCount}
        sbomFormat={sbomFormat}
      />

      <CollapsibleLogCard log={log} running={running} title={ts ? "SBOM log" : "SBOM logs"} />
    </div>
  );
}
