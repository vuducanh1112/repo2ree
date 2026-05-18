import { useMemo } from "react";
import type { ReeAssemblyRunParams } from "../../../../../core/ree-assembly/assemblyTypes";
import { resolvedRuntimePath } from "../../../../../core/ree-assembly/buildRuntimeUiState";
import {
  isRuntimeTarballPath,
  resolvedSbomPath,
  summarizeSbom,
} from "../../../../../core/ree-assembly/sbomUiState";
import { workspaceFileExists } from "../../../../../core/workspace/fileTreeTraversal";
import { Ic } from "../../../shared/components/Icon";
import {
  lgColors,
  lgNextButton,
  lgOutcomeBadge,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { PAGE } from "../../state/pages";
import {
  RUNTIME_ENV_COLOR,
  RuntimeEnvironmentShell,
} from "../runtime-environment/RuntimeEnvironmentShell";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import {
  RuntimeScanTargetCard,
  SbomOutputCard,
  SbomReadinessAside,
  SbomRunConsole,
  SbomSummaryAside,
} from "./sections";

export function PageGenerateSBOM({
  assemblyStep,
  ree,
  inclusionState,
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
}: AssemblyPageProps) {
  const files = workspaceFiles || [];

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeIsTarball = !!runtimePath && isRuntimeTarballPath(runtimePath);
  const runtimeBundled = inclusionState.runtime === "included";

  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomNode = sbomPath ? findFileByPath(files, sbomPath) : null;
  const sbomSummary = useMemo(() => summarizeSbom(sbomNode), [sbomNode]);
  const { format: sbomFormat, pkgCount } = sbomSummary;

  const sbomParams: ReeAssemblyRunParams<"sbom"> = {
    ...(params as ReeAssemblyRunParams<"sbom">),
    produced_runtime_path: runtimePath,
  };

  const buildReady = !!runtimePath && runtimePathExists;

  const headerBadges = (
    <>
      {runtimePath && (
        <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{runtimePath}</span>
      )}
      <span style={lgStatusBadge(buildReady)}>{buildReady ? "Build ready" : "Build pending"}</span>
      <span style={lgStatusBadge(!!sbomPath && !!sbomNode)}>
        {sbomPath && sbomNode ? "SBOM ready" : "SBOM pending"}
      </span>
      {runDone && badge && (
        <span style={lgOutcomeBadge(badge.color, badge.bg)}>
          {Ic.check(11)} {badge.label}
        </span>
      )}
    </>
  );

  const headerRight = runDone && ts ? <LastRunStamp label="Last generated" ts={ts} /> : null;

  return (
    <RuntimeEnvironmentShell
      active={PAGE.SBOM}
      buildReady={!!runtimePath && runtimePathExists}
      sbomReady={!!sbomPath && !!sbomNode}
      onGo={onGo}
      headerBadges={headerBadges}
      headerRight={headerRight}
      main={
        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <GlassSectionHeader
              icon={Ic.cpu(19)}
              color={RUNTIME_ENV_COLOR}
              title="Scan Target"
              subtitle="SBOM generation reads the runtime artifact selected on the build tab."
            />

            <RuntimeScanTargetCard
              runtimePath={runtimePath}
              runtimePathExists={runtimePathExists}
              runtimeIsTarball={runtimeIsTarball}
              runtimeBundled={runtimeBundled}
              color={RUNTIME_ENV_COLOR}
              onGoBuild={() => onGo?.(PAGE.BUILD)}
            />

            <div style={{ marginTop: 22 }}>
              <GlassSectionHeader
                icon={Ic.package(19)}
                color={RUNTIME_ENV_COLOR}
                title="Produced SBOM"
                subtitle="The generated SPDX JSON file attached to ree.sbom."
              />

              <SbomOutputCard
                color={RUNTIME_ENV_COLOR}
                sbomPath={sbomPath}
                sbomFilePresent={!!sbomNode}
                pkgCount={pkgCount}
                sbomFormat={sbomFormat}
              />
            </div>

            <div style={{ marginTop: 22 }}>
              <CollapsibleLogCard
                log={log}
                running={running}
                title={ts ? "SBOM log" : "SBOM logs"}
              />
            </div>
          </div>

          <div style={lgStyles.footer}>
            <span style={{ color: lgColors.textMuted, fontSize: 12, fontFamily: F.sans }}>
              {sbomPath && sbomNode
                ? "SBOM is ready for packaging and review."
                : "Generate the SBOM after the runtime artifact exists in the workspace."}
            </span>
            <button type="button" onClick={() => onGo?.(PAGE.ACTIVATION)} style={lgNextButton()}>
              Next: Test Activation {Ic.chevR(15)}
            </button>
          </div>
        </section>
      }
      aside={
        <>
          <SbomRunConsole
            color={RUNTIME_ENV_COLOR}
            runtimePath={runtimePath}
            runtimePathExists={runtimePathExists}
            running={running}
            runDone={runDone}
            missing={missing}
            onRun={() => onRun(assemblyStep.key, sbomParams)}
            onCancel={onCancel ? () => onCancel(assemblyStep.key) : undefined}
            onGoFields={onGoFields}
          />
          <SbomSummaryAside
            runtimePath={runtimePath}
            runtimePathExists={runtimePathExists}
            runtimeBundled={runtimeBundled}
            sbomPath={sbomPath}
            sbomNode={sbomNode}
            pkgCount={pkgCount}
            sbomFormat={sbomFormat}
            runDone={runDone}
          />
          <SbomReadinessAside
            runtimePath={runtimePath}
            runtimePathExists={runtimePathExists}
            sbomPath={sbomPath}
          />
        </>
      }
    />
  );
}
