import type { RuntimeEntry } from "@core/ree/ReeSpec";
import { deriveRuntimeFileSize, resolvedRuntimePath } from "@core/ree-assembly/buildRuntimeUiState";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { workspaceFileExists } from "@core/workspace/fileTreeTraversal";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgPageColors,
  lgPageRoot,
  lgPillChip,
  lgStyles,
  pageIconTint,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useCallback, useMemo } from "react";
import { GlassPageHeader } from "../../components/GlassPageHeader";
import { GlassSectionHeader } from "../../components/GlassSectionHeader";
import { SubstratePicker } from "../../components/SubstratePicker";
import { RuntimeArtifactCard } from "../build-runtime/sections";
import { findFileByPath } from "../sharedAssemblyHelpers";

const RUNTIME_PAGE_COLOR = lgPageColors.runtimeEnv;

interface RuntimeEnvironmentPageProps {
  ree: ReeEditorViewModel;
  workspaceFiles?: FileTreeNode[];
  onReeSpecChange: (updater: (current: ReeEditorViewModel) => ReeEditorViewModel) => void;
}

// Overview of the runtime: artifact + substrate. Both are also editable from the
// Build Runtime page, which is the primary entry point; this page is a dedicated
// view for inspecting or changing them without going through the build flow.
export function PageRuntimeEnvironment({
  ree,
  workspaceFiles,
  onReeSpecChange,
}: RuntimeEnvironmentPageProps) {
  const files = workspaceFiles || [];

  const runtimeEntry: RuntimeEntry = ree.runtime_entry;

  const finalRuntime = resolvedRuntimePath(ree.runtime);
  const runtimePathExists = finalRuntime ? workspaceFileExists(files, finalRuntime) : false;
  const finalRuntimeFile = useMemo(
    () => (finalRuntime ? findFileByPath(files, finalRuntime) : null),
    [files, finalRuntime],
  );
  const finalRuntimeSize = useMemo(
    () => deriveRuntimeFileSize(finalRuntimeFile),
    [finalRuntimeFile],
  );

  const handleRuntimeChange = useCallback(
    (path: string) => onReeSpecChange((current) => ({ ...current, runtime: path })),
    [onReeSpecChange],
  );

  const handleEntryChange = useCallback(
    (entry: RuntimeEntry) => onReeSpecChange((current) => ({ ...current, runtime_entry: entry })),
    [onReeSpecChange],
  );

  return (
    <div style={lgPageRoot}>
      <GlassPageHeader
        icon={Ic.cpu(24)}
        iconTint={pageIconTint(RUNTIME_PAGE_COLOR)}
        title="Runtime Environment"
        subtitle="The execution substrate the whole REE runs on — its artifact and how the workbench enters it."
        badges={
          finalRuntime ? (
            <span style={{ ...lgPillChip(true), fontFamily: F.mono }}>{finalRuntime}</span>
          ) : null
        }
      />

      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <section style={{ ...lgStyles.panel, overflow: "hidden" }}>
          <div style={lgStyles.sectionBody}>
            <GlassSectionHeader
              icon={Ic.archive(19)}
              color={RUNTIME_PAGE_COLOR}
              title="Runtime Artifact"
              subtitle="The file the build produced, consumed by SBOM, activation and experiments."
            />

            <RuntimeArtifactCard
              runtimePath={finalRuntime}
              runtimeSize={finalRuntimeSize}
              runtimePathExists={runtimePathExists}
              files={files}
              onRuntimeChange={handleRuntimeChange}
            />

            <div style={{ marginTop: 22 }}>
              <GlassSectionHeader
                icon={Ic.cpu(19)}
                color={RUNTIME_PAGE_COLOR}
                title="Runtime Substrate"
                subtitle="How the workbench enters the runtime. Shared by activation and all experiments."
              />
              <div style={{ marginTop: 10 }}>
                <SubstratePicker
                  entry={runtimeEntry}
                  accent={RUNTIME_PAGE_COLOR}
                  onChange={handleEntryChange}
                />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
