import { PAGE } from "../../constants/pages";
import { defaultParamsForService, SERVICES } from "../../constants/services";
import type {
  ActionStates,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Ree,
  ReeFile,
  ServiceLogs,
  ServiceParams,
  SourceUploadCommit,
  Timestamps,
} from "../../types";
import { PageArchive as ArchivePage } from "../archive/PageArchive";
import { PageFiles as FilesPage } from "../files/PageFiles";
import { PageOverview } from "../overview/PageOverview";
import {
  PageBuildRuntime,
  PageEvaluate,
  PageGenerateSBOM,
  PageMetadataEntry,
  PageSourceRepoEntry,
  PageTestActivation,
  type ServicePageProps,
} from "./screens";
import { explorerPageForField } from "./utils/navigation";
import { missingRequirements } from "./utils/requirements";

const SERVICE_PAGE_COMPONENTS: Record<string, (props: ServicePageProps) => JSX.Element> = {
  evaluate: (props) => <PageEvaluate {...props} />,
  build: (props) => <PageBuildRuntime {...props} />,
  sbom: (props) => <PageGenerateSBOM {...props} />,
  activation: (props) => <PageTestActivation {...props} />,
};

interface ExplorerMainContentProps {
  page: ExplorerPage;
  ree: Ree;
  level: number;
  locked: boolean;
  repoMode: "url" | "upload";
  focusedField: string | null;
  badges: Badges;
  timestamps: Timestamps;
  serviceLogs: ServiceLogs;
  serviceParams: ServiceParams;
  actionStates: ActionStates;
  virtualFiles: FileTreeNode[];
  immutableSourceSnapshotFiles: FileTreeNode[];
  currentReeFiles: ReeFile[];
  onReeChange: React.Dispatch<React.SetStateAction<Ree>>;
  onLockedChange: React.Dispatch<React.SetStateAction<boolean>>;
  onRepoModeChange: React.Dispatch<React.SetStateAction<"url" | "upload">>;
  onPageChange: React.Dispatch<React.SetStateAction<ExplorerPage>>;
  onFocusedFieldChange: React.Dispatch<React.SetStateAction<string | null>>;
  onVirtualFilesChange: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  onServiceParamsChange: React.Dispatch<React.SetStateAction<ServiceParams>>;
  onSeal: () => void;
  onDownloadRee: () => void;
  onPreviewReviewer: () => void;
  onDownloadSourceFiles: (originType: Ree["source_type"]) => void;
  onWorkspaceUpload: (payload: SourceUploadCommit) => void;
  onRemoveWorkspaceSource: () => void;
  onRunAction: (key: string, params?: Record<string, unknown>) => Promise<void>;
}

export function ExplorerMainContent({
  page,
  ree,
  level,
  locked,
  repoMode,
  focusedField,
  badges,
  timestamps,
  serviceLogs,
  serviceParams,
  actionStates,
  virtualFiles,
  immutableSourceSnapshotFiles,
  currentReeFiles,
  onReeChange,
  onLockedChange,
  onRepoModeChange,
  onPageChange,
  onFocusedFieldChange,
  onVirtualFilesChange,
  onServiceParamsChange,
  onSeal,
  onDownloadRee,
  onPreviewReviewer,
  onDownloadSourceFiles,
  onWorkspaceUpload,
  onRemoveWorkspaceSource,
  onRunAction,
}: ExplorerMainContentProps) {
  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        minWidth: 0,
        position: "relative",
        background: "linear-gradient(135deg, #f0f4ff 0%, #f8f9ff 35%, #fff5f9 65%, #f4f8ff 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            width: 480,
            height: 320,
            borderRadius: "50%",
            top: -80,
            left: "10%",
            background: "radial-gradient(ellipse, #c7d9ff88 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 360,
            height: 280,
            borderRadius: "50%",
            top: 20,
            right: "5%",
            background: "radial-gradient(ellipse, #e0d0ff66 0%, transparent 70%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 300,
            height: 200,
            borderRadius: "50%",
            top: 160,
            left: "35%",
            background: "radial-gradient(ellipse, #ffd6e855 0%, transparent 70%)",
          }}
        />
      </div>
      <div
        style={{
          position: "relative",
          zIndex: 1,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        {(page === PAGE.OVERVIEW || page === PAGE.SEAL) && (
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <PageOverview
              ree={ree}
              onReeChange={onReeChange}
              level={level}
              onNavigate={(key) => onPageChange(key)}
              badges={badges}
              timestamps={timestamps}
              onGoField={(key) => {
                onPageChange(explorerPageForField(String(key)));
                onFocusedFieldChange(String(key));
              }}
              files={virtualFiles}
              snapshotFiles={immutableSourceSnapshotFiles}
              locked={locked}
              onSeal={onSeal}
              onPreviewReviewer={onPreviewReviewer}
              onDownloadRee={ree._sealedAt ? onDownloadRee : undefined}
            />
          </div>
        )}
        {page === PAGE.SOURCE && (
          <PageSourceRepoEntry
            ree={ree}
            locked={locked}
            repoMode={repoMode}
            badges={badges}
            actionStates={actionStates}
            focusedField={focusedField}
            onReeChange={onReeChange}
            onRepoModeChange={onRepoModeChange}
            onGoService={(key) => onPageChange(key)}
            onFocusedFieldChange={onFocusedFieldChange}
            onDownloadSource={(originType) => onDownloadSourceFiles(originType)}
            onWorkspaceUpload={onWorkspaceUpload}
            onRemoveWorkspaceSource={onRemoveWorkspaceSource}
          />
        )}
        {page === PAGE.METADATA && (
          <PageMetadataEntry
            ree={ree}
            locked={locked}
            badges={badges}
            focusedField={focusedField}
            onReeChange={onReeChange}
            onLockedChange={onLockedChange}
            onGoService={(key) => onPageChange(key)}
            onFocusedFieldChange={onFocusedFieldChange}
          />
        )}
        {SERVICES.map((svc) => {
          if (page !== svc.key) {
            return null;
          }

          const ServicePageComponent = SERVICE_PAGE_COMPONENTS[svc.key];
          if (!ServicePageComponent) {
            return null;
          }

          const params = serviceParams[svc.key] ?? defaultParamsForService(svc);
          const missing = missingRequirements(svc, ree);

          const setParam = (paramKey: string, value: unknown) => {
            onServiceParamsChange((prev) => ({
              ...prev,
              [svc.key]: {
                ...(prev[svc.key] ?? defaultParamsForService(svc)),
                [paramKey]: value,
              },
            }));
          };

          return (
            <div
              key={svc.key}
              style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
            >
              <ServicePageComponent
                svc={svc}
                ree={ree}
                badges={badges}
                virtualFiles={virtualFiles}
                log={serviceLogs[svc.key]}
                running={actionStates[svc.key] === "loading"}
                runDone={!!badges[svc.key]}
                badge={badges[svc.key] ? svc.badge : null}
                ts={timestamps[svc.key]}
                onRun={onRunAction}
                onGo={(key) => onPageChange(key)}
                onGoFields={() => {
                  const sourceFieldKeys: (keyof Ree)[] = [
                    "origin_url",
                    "source_type",
                    "_sourceAvailable",
                  ];
                  const hasSourceGap = missing.some((requirement) =>
                    sourceFieldKeys.includes(requirement.field),
                  );
                  onPageChange(hasSourceGap ? PAGE.SOURCE : PAGE.METADATA);
                }}
                onReeChange={onReeChange}
                onFilesChange={onVirtualFilesChange}
                missing={missing}
                params={params}
                setParam={setParam}
              />
            </div>
          );
        })}
        {page === PAGE.ARCHIVE && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <ArchivePage
              ree={ree}
              badges={badges}
              logs={serviceLogs}
              actionStates={actionStates}
              onRun={onRunAction}
              onGo={(key) => onPageChange(key)}
            />
          </div>
        )}
        {page === PAGE.FILES && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <FilesPage files={virtualFiles} reeFiles={currentReeFiles} />
          </div>
        )}
      </div>
    </main>
  );
}
