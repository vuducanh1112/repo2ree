import { resolvedRuntimePath } from "@core/ree-steps/buildRuntimeUiState";
import { isRuntimeTarballPath, resolvedSbomPath, summarizeSbom } from "@core/ree-steps/sbomUiState";
import type { ReeStepRunParams } from "@core/ree-steps/stepRunParams";
import { findFileByWorkspacePath, workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { useMemo } from "react";
import { Ic } from "../../shared/components/Icon";
import {
  lgAccentActionButton,
  lgColors,
  lgInfoBanner,
  lgStatusBadge,
} from "../../theme/lightGlassTheme";
import { CollapsibleLogCard } from "../components/CollapsibleLogCard";
import { MissingInputsBanner } from "../components/MissingInputsBanner";
import { OutcomeBadge } from "../components/OutcomeBadge";
import { RunActionButton } from "../components/RunActionButton";
import { useStepPageController } from "../hooks/useStepPageController";
import { RuntimeScanTargetCard, SbomOutputCard } from "../pages/generate-sbom/sections";
import type { AppShellPageContainerProps } from "../pages/pageContainers/shared";
import { HubPanel, HubPanelHeader } from "./HubPanel";

const SBOM_PAGE_COLOR = "#16a34a";

type SbomHubPanelProps = Pick<
  AppShellPageContainerProps,
  "ree" | "workspaceRemote" | "stepRuns" | "uiChrome" | "commands"
> & {
  onClose: () => void;
};

// SBOM is essentially a one-press action, so it opens as a compact floating
// panel in the hub — like the seal — rather than docking a full-size page.
export function SbomHubPanel({
  ree,
  workspaceRemote,
  stepRuns,
  uiChrome,
  commands,
  onClose,
}: SbomHubPanelProps) {
  const controller = useStepPageController({ ree, stepRuns, uiChrome, commands });

  const files = workspaceRemote.workspaceFiles || [];
  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeIsTarball = !!runtimePath && isRuntimeTarballPath(runtimePath);

  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomNode = sbomPath ? findFileByWorkspacePath(files, sbomPath) : null;
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
                commands.onRunStep(controller.step.key, {
                  ...(controller.params as ReeStepRunParams<"sbom">),
                  produced_runtime_path: runtimePath,
                })
              }
              onCancel={() => commands.onCancelAction(controller.step.key)}
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

type Controller = NonNullable<ReturnType<typeof useStepPageController>>;

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
  const { log, running, badge, ts, missing } = controller;

  const buildReady = !!runtimePath && runtimePathExists;
  const sbomReady = !!sbomPath && sbomFilePresent;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <span style={lgStatusBadge(buildReady)}>
          {buildReady ? "Build ready" : "Build pending"}
        </span>
        <span style={lgStatusBadge(sbomReady)}>{sbomReady ? "SBOM ready" : "SBOM pending"}</span>
        {badge && <OutcomeBadge badge={badge} />}
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
