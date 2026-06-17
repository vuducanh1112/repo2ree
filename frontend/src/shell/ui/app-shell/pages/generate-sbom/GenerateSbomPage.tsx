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
  lgInfoBanner,
  lgOutcomeBadge,
  lgPillChip,
  lgPrimaryActionButton,
  lgStatusBadge,
  lgStyles,
} from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { CollapsibleLogCard } from "../../components/CollapsibleLogCard";
import { GlassCancelButton } from "../../components/GlassCancelButton";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { LastRunStamp } from "../../components/LastRunStamp";
import { MissingInputsBanner } from "../runtime-environment/MissingInputsBanner";
import { findFileByPath } from "../sharedAssemblyHelpers";
import type { AssemblyPageProps } from "../sharedAssemblyUi";
import { RuntimeScanTargetCard, SbomOutputCard } from "./sections";

const SBOM_PAGE_COLOR = "#16a34a";

function SbomRunControls({
  running,
  runDone,
  disabled,
  onRun,
  onCancel,
}: {
  running: boolean;
  runDone: boolean;
  disabled: boolean;
  onRun: () => void;
  onCancel?: () => void;
}) {
  const label = running ? "Generating…" : runDone ? "Regenerate SBOM" : "Generate SBOM";
  return (
    <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
      <button
        type="button"
        onClick={onRun}
        disabled={disabled}
        style={lgPrimaryActionButton(disabled)}
      >
        <span
          style={{ display: "flex", animation: running ? "spin 0.9s linear infinite" : "none" }}
        >
          {running ? Ic.loader(14) : Ic.play(14)}
        </span>
        {label}
      </button>
      {running && onCancel && <GlassCancelButton onClick={onCancel} />}
    </div>
  );
}

export function PageGenerateSBOM({
  assemblyStep,
  ree,
  workspaceFiles,
  log,
  running,
  runDone,
  badge,
  ts,
  onRun,
  onCancel,
  onGoFields,
  missing,
  params,
}: AssemblyPageProps) {
  const files = workspaceFiles || [];

  const runtimePath = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = runtimePath ? workspaceFileExists(files, runtimePath) : false;
  const runtimeIsTarball = !!runtimePath && isRuntimeTarballPath(runtimePath);

  const sbomPath = resolvedSbomPath(ree.sbom);
  const sbomNode = sbomPath ? findFileByPath(files, sbomPath) : null;
  const sbomSummary = useMemo(() => summarizeSbom(sbomNode), [sbomNode]);
  const { format: sbomFormat, pkgCount } = sbomSummary;

  const sbomParams: ReeAssemblyRunParams<"sbom"> = {
    ...(params as ReeAssemblyRunParams<"sbom">),
    produced_runtime_path: runtimePath,
  };

  const buildReady = !!runtimePath && runtimePathExists;
  const hasMissing = missing.length > 0;
  const disabled = running || hasMissing || !runtimePathExists;

  return (
    <div style={pageRoot}>
      <GlassPageHeader
        icon={Ic.package(24)}
        iconTint={{
          color: SBOM_PAGE_COLOR,
          border: `${SBOM_PAGE_COLOR}55`,
          shadow: `${SBOM_PAGE_COLOR}28`,
        }}
        title="Generate SBOM"
        subtitle="Scan the built runtime and produce a software inventory."
        badges={
          <>
            {runtimePath && (
              <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{runtimePath}</span>
            )}
            <span style={lgStatusBadge(buildReady)}>
              {buildReady ? "Build ready" : "Build pending"}
            </span>
            <span style={lgStatusBadge(!!sbomPath && !!sbomNode)}>
              {sbomPath && sbomNode ? "SBOM ready" : "SBOM pending"}
            </span>
            {runDone && badge && (
              <span style={lgOutcomeBadge(badge.color, badge.bg)}>
                {Ic.check(11)} {badge.label}
              </span>
            )}
          </>
        }
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
            {runDone && ts && <LastRunStamp label="Last generated" ts={ts} />}
            <SbomRunControls
              running={running}
              runDone={runDone}
              disabled={disabled}
              onRun={() => onRun(assemblyStep.key, sbomParams)}
              onCancel={onCancel ? () => onCancel(assemblyStep.key) : undefined}
            />
          </div>
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <MissingInputsBanner missing={missing} onGoFields={onGoFields} />

        {runtimePath && !runtimePathExists && (
          <div style={lgInfoBanner("danger")}>
            <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
            <span style={{ fontSize: 12, color: lgColors.danger }}>
              Runtime file must exist before SBOM generation can run.
            </span>
          </div>
        )}

        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <GlassSectionHeader
              icon={Ic.cpu(19)}
              color={SBOM_PAGE_COLOR}
              title="Scan Target"
              subtitle="SBOM generation reads the runtime artifact selected on the build tab."
            />

            <RuntimeScanTargetCard
              runtimePath={runtimePath}
              runtimePathExists={runtimePathExists}
              runtimeIsTarball={runtimeIsTarball}
              color={SBOM_PAGE_COLOR}
            />

            <div style={{ marginTop: 22 }}>
              <GlassSectionHeader
                icon={Ic.package(19)}
                color={SBOM_PAGE_COLOR}
                title="Produced SBOM"
                subtitle="The generated SPDX JSON file attached to ree.sbom."
              />

              <SbomOutputCard
                color={SBOM_PAGE_COLOR}
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
          </div>
        </section>
      </div>
    </div>
  );
}

const pageRoot: React.CSSProperties = {
  height: "100%",
  minHeight: 0,
  overflow: "auto",
  padding: "46px 36px 32px",
  color: lgColors.text,
};
