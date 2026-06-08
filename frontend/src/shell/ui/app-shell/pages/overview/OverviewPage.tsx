import React, { useRef } from "react";
import type { ArtifactStatus } from "../../../../../core/artifact/ArtifactStatus";
import type { InclusionOpts } from "../../../../../core/ree/InclusionOpts";
import type { Badges, LogEntry, Timestamps } from "../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../core/ree-editor/reeEditorViewModel";
import type { EvaluationState } from "../../../../../core/review/EvaluationState";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import { listTreeFiles } from "../../../../../core/workspace/fileTreeTraversal";
import type { WorkspaceSourceState } from "../../../../../core/workspace/WorkspaceSourceState";
import { lgStyles } from "../../../theme/lightGlassTheme";
import type { AppShellPage } from "../../state/pages";
import {
  OverviewColumns,
  OverviewFieldsPanel,
  OverviewHeader,
  OverviewLevelStrip,
} from "./OverviewPageSections";

interface PageOverviewProps {
  ree: ReeEditorViewModel;
  onWorkspaceSourceStateChange: React.Dispatch<React.SetStateAction<WorkspaceSourceState>>;
  onArtifactStatusChange: React.Dispatch<React.SetStateAction<ArtifactStatus>>;
  evaluation: EvaluationState;
  onNavigate: (key: AppShellPage) => void;
  badges?: Badges;
  timestamps?: Timestamps;
  onGoField: (key: string) => void;
  files?: FileTreeNode[];
  snapshotFiles?: FileTreeNode[];
  locked?: boolean;
  onSeal: (inclusionOpts: InclusionOpts) => void;
  sealRunning?: boolean;
  sealLog?: LogEntry | null;
  onPreviewReviewer: () => void;
  onDownloadRee?: () => void;
  onReleaseWorkbench?: () => void;
}

export function PageOverview({
  ree,
  onWorkspaceSourceStateChange,
  onArtifactStatusChange,
  evaluation,
  onNavigate,
  badges = {},
  timestamps = {},
  onGoField,
  files = [],
  snapshotFiles = [],
  locked = false,
  onSeal,
  sealRunning = false,
  sealLog = null,
  onPreviewReviewer,
  onDownloadRee,
  onReleaseWorkbench,
}: PageOverviewProps) {
  const cableContainerRef = useRef<HTMLDivElement>(null);
  const sourceRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const hbomRef = useRef<HTMLDivElement>(null);
  const podColumnRef = useRef<HTMLDivElement>(null);
  const podSvgRef = useRef<SVGSVGElement>(null);
  const swhRef = useRef<HTMLDivElement>(null);
  const evaluateRef = useRef<HTMLDivElement>(null);
  const sbomRef = useRef<HTMLDivElement>(null);
  const sealRef = useRef<HTMLDivElement>(null);
  const archiveRef = useRef<HTMLDivElement>(null);
  const activationRef = useRef<HTMLDivElement>(null);
  const experimentsRef = useRef<HTMLDivElement>(null);

  const [podSize, setPodSize] = React.useState(480);
  React.useEffect(() => {
    const el = podColumnRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      setPodSize(Math.min(640, Math.max(260, w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const allFiles = listTreeFiles(snapshotFiles);
  const fileCount = allFiles.length;
  const totalBytes = allFiles.reduce(
    (totalSize, file) =>
      totalSize + (file.content ? new TextEncoder().encode(file.content).length : 0),
    0,
  );

  return (
    <div style={lgStyles.pageRoot}>
      <div style={lgStyles.pageFrame}>
        <OverviewHeader ree={ree} evaluation={evaluation} badges={badges} />
        <OverviewColumns
          ree={ree}
          evaluation={evaluation}
          badges={badges}
          timestamps={timestamps}
          files={files}
          fileCount={fileCount}
          totalBytes={totalBytes}
          locked={locked}
          podSize={podSize}
          onGoField={onGoField}
          onNavigate={onNavigate}
          onWorkspaceSourceStateChange={onWorkspaceSourceStateChange}
          onArtifactStatusChange={onArtifactStatusChange}
          onSeal={onSeal}
          sealRunning={sealRunning}
          sealLog={sealLog}
          onPreviewReviewer={onPreviewReviewer}
          onDownloadRee={onDownloadRee}
          onReleaseWorkbench={onReleaseWorkbench}
          refs={{
            cableContainerRef,
            sourceRef,
            runtimeRef,
            leftPanelRef,
            hbomRef,
            swhRef,
            evaluateRef,
            sbomRef,
            sealRef,
            archiveRef,
            activationRef,
            experimentsRef,
            podSvgRef,
            podColumnRef,
          }}
        />
        <OverviewLevelStrip evaluation={evaluation} />
        <OverviewFieldsPanel ree={ree} />
      </div>
    </div>
  );
}
