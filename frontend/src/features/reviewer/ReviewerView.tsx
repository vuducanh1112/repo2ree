import { useEffect, useMemo, useState } from "react";
import { ApiClient, mapRunLogsToLegacy, ReviewsApi } from "../../api";
import { Ic } from "../../components/Icon";
import { LevelBadge } from "../../components/LevelBadge";
import { LEVELS } from "../../constants/levels";
import { C, F, hoverBg, hoverColor, S_SECTION_LABEL_SMALL } from "../../constants/theme";
import type { LogLine, Ree, ReeFile } from "../../types/ree";
import type { Level, ServiceParamValue, StepState } from "../../types/workflowSteps";
import type { FileTreeNode } from "../../types/workspace";
import { hbomSummaryLines } from "../../utils/hbom";
import { PageFiles } from "../files/PageFiles";
import {
  MetaRow,
  REACTIVATION_STEPS,
  type ReactivationParams,
  type ReactivationStepKey,
  RvProvenanceChain,
  RvStepCard,
  RvVerdictBanner,
} from "./reviewerSupport";

interface ReviewerViewProps {
  reviewId?: string;
  ree?: Ree;
  reviewFiles?: Array<{ path: string; size?: number }>;
  reviewWorkspaceFiles?: Array<{ path: string; size?: number }>;
  onBack: () => void;
  defaultRee: Ree;
  PodOrbitControl: React.ComponentType<{
    level: number;
    levelMeta: Level;
    stepStates: Record<string, StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

function buildTreeFromPaths(files: Array<{ path: string; size?: number }>, idPrefix: string) {
  const roots: FileTreeNode[] = [];
  for (const file of files) {
    const parts = (file.path || "").split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let cursor = roots;
    let currentPrefix = "";
    for (let i = 0; i < parts.length - 1; i += 1) {
      const part = parts[i];
      currentPrefix = currentPrefix ? `${currentPrefix}/${part}` : part;
      let folder = cursor.find((node) => node.type === "folder" && node.name === part);
      if (!folder) {
        folder = {
          id: `${idPrefix}-dir-${currentPrefix}`,
          name: part,
          type: "folder",
          children: [],
        };
        cursor.push(folder);
      }
      if (!folder.children) {
        folder.children = [];
      }
      cursor = folder.children;
    }

    const fileName = parts[parts.length - 1];
    const fileNode: FileTreeNode = {
      id: `${idPrefix}-file-${file.path}`,
      name: fileName,
      type: "file",
      size: file.size,
      tag: "workspace",
    };
    const existingIdx = cursor.findIndex((node) => node.type === "file" && node.name === fileName);
    if (existingIdx >= 0) {
      cursor[existingIdx] = fileNode;
    } else {
      cursor.push(fileNode);
    }
  }
  return roots;
}

export function ReviewerView({
  reviewId,
  ree: reeInput,
  reviewFiles = [],
  reviewWorkspaceFiles = [],
  onBack,
  defaultRee,
  PodOrbitControl,
}: ReviewerViewProps) {
  const ree = reeInput || defaultRee;
  const [reviewerPage, setReviewerPage] = useState<"review" | "files">("review");
  const [reviewRootFilesState, setReviewRootFilesState] = useState(reviewFiles);
  const [reviewWorkspaceFilesState, setReviewWorkspaceFilesState] = useState(reviewWorkspaceFiles);
  const level = ree._evalLevel ?? 5;
  const levelMeta = LEVELS[Math.min(level, 7)];
  const sealDate = ree._sealedAt
    ? new Date(ree._sealedAt).toLocaleString([], {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "unknown";

  const [stepStates, setStepStates] = useState<Partial<Record<ReactivationStepKey, StepState>>>({});
  const [stepLogs, setStepLogs] = useState<Partial<Record<ReactivationStepKey, LogLine[]>>>({});
  const [stepRunIds, setStepRunIds] = useState<Partial<Record<ReactivationStepKey, string>>>({});
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
  const apiClient = useMemo(
    () =>
      new ApiClient({
        baseUrl: env.VITE_API_BASE_URL || "",
      }),
    [env.VITE_API_BASE_URL],
  );
  const reviewsApi = useMemo(() => new ReviewsApi(apiClient), [apiClient]);

  useEffect(() => {
    setReviewRootFilesState(reviewFiles);
  }, [reviewFiles]);

  useEffect(() => {
    setReviewWorkspaceFilesState(reviewWorkspaceFiles);
  }, [reviewWorkspaceFiles]);

  const refreshReviewFiles = async () => {
    if (!reviewId) return;
    const detail = await reviewsApi.getReview(reviewId);
    setReviewRootFilesState(
      (detail.files || []).map((file) => ({ path: file.path, size: file.size })),
    );
    setReviewWorkspaceFilesState(
      (detail.workspaceFiles || []).map((file) => ({ path: file.path, size: file.size })),
    );
  };
  const initParams = (): Record<ReactivationStepKey, ReactivationParams> =>
    Object.fromEntries(
      REACTIVATION_STEPS.map((step) => [
        step.key,
        Object.fromEntries((step.params || []).map((param) => [param.key, param.default])),
      ]),
    ) as Record<ReactivationStepKey, ReactivationParams>;
  const [stepParams, setStepParams] =
    useState<Record<ReactivationStepKey, ReactivationParams>>(initParams);

  const setParam = (stepKey: ReactivationStepKey, paramKey: string, val: ServiceParamValue) =>
    setStepParams((p) => ({ ...p, [stepKey]: { ...p[stepKey], [paramKey]: val } }));

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
  const isTerminalStatus = (status: string) =>
    status === "succeeded" || status === "failed" || status === "canceled";

  const runBackendStep = async (key: ReactivationStepKey): Promise<LogLine[]> => {
    if (!reviewId) {
      const localStep = REACTIVATION_STEPS.find((reactivationStep) => reactivationStep.key === key);
      return localStep ? localStep.logLines(ree, stepParams[key]) : [];
    }

    if (key === "acquire_source" && ree._sourceIncluded) {
      return [
        { type: "info", msg: "Source already included in uploaded archive." },
        { type: "ok", msg: "Source acquisition skipped ✓" },
      ];
    }

    let runId = "";
    if (key === "acquire_source") {
      if (!ree.origin_url || !ree.source_type) {
        throw new Error("origin_url and source_type are required to acquire source");
      }
      const sourceRun = await reviewsApi.acquireSource(reviewId);
      runId = sourceRun.runId;
    } else if (key === "build_runtime") {
      const buildRun = await reviewsApi.createBuildRuntimeRun(reviewId, {
        build_runtime_script_path: ree.build_runtime_script,
        produced_runtime_path: ree.runtime,
      });
      runId = buildRun.runId;
    } else {
      const activationRun = await reviewsApi.createActivationTestRun(reviewId, {
        activation_script_path: ree.activation_script,
      });
      runId = activationRun.runId;
    }
    setStepRunIds((prev) => ({ ...prev, [key]: runId }));

    const collected: LogLine[] = [];
    const seen = new Set<string>();
    let cursor: string | undefined;

    for (let i = 0; i < 120; i += 1) {
      const logs = await reviewsApi.listRunLogs(reviewId, runId, cursor);
      const mapped = mapRunLogsToLegacy(logs.entries);
      for (const line of mapped) {
        const keyPart = `${line.ts || ""}::${line.type}::${line.msg}`;
        if (seen.has(keyPart)) continue;
        seen.add(keyPart);
        collected.push(line);
      }
      cursor = logs.nextCursor;
      setStepLogs((prevLogs) => ({ ...prevLogs, [key]: [...collected] }));

      if (isTerminalStatus(logs.runStatus)) {
        while (logs.hasMore && cursor) {
          const nextLogs = await reviewsApi.listRunLogs(reviewId, runId, cursor);
          for (const line of mapRunLogsToLegacy(nextLogs.entries)) {
            const keyPart = `${line.ts || ""}::${line.type}::${line.msg}`;
            if (seen.has(keyPart)) continue;
            seen.add(keyPart);
            collected.push(line);
          }
          cursor = nextLogs.nextCursor;
        }
        const run = await reviewsApi.getRun(reviewId, runId);
        if (run.status === "canceled") {
          collected.push({ type: "warn", msg: "Run canceled" });
        } else if (run.status !== "succeeded") {
          collected.push({ type: "err", msg: `Run ended with status: ${run.status}` });
        }
        setStepRunIds((prev) => ({ ...prev, [key]: "" }));
        return collected;
      }

      await sleep(i < 10 ? 700 : i < 40 ? 1200 : 2000);
    }

    collected.push({ type: "warn", msg: "Run polling timed out before completion" });
    setStepRunIds((prev) => ({ ...prev, [key]: "" }));
    return collected;
  };

  const runStep = async (key: ReactivationStepKey, params: ReactivationParams) => {
    void params;
    if (!REACTIVATION_STEPS.find((reactivationStep) => reactivationStep.key === key)) return false;
    setStepStates((prevStates) => ({ ...prevStates, [key]: "loading" }));
    setStepLogs((prevLogs) => ({ ...prevLogs, [key]: [] }));
    try {
      const lines = await runBackendStep(key);
      setStepLogs((prevLogs) => ({ ...prevLogs, [key]: lines }));
      const hasError = lines.some((line) => line.type === "err");
      setStepStates((prevStates) => ({ ...prevStates, [key]: hasError ? "idle" : "done" }));
      if (!hasError) {
        try {
          await refreshReviewFiles();
        } catch {
          setStepLogs((prevLogs) => ({
            ...prevLogs,
            [key]: [
              ...(prevLogs[key] || []),
              { type: "warn", msg: "Run succeeded, but failed to refresh file list" },
            ],
          }));
        }
      }
      return !hasError;
    } catch (error) {
      setStepLogs((prevLogs) => ({
        ...prevLogs,
        [key]: [
          {
            type: "err",
            msg: error instanceof Error ? error.message : "Failed to execute step",
          },
        ],
      }));
      setStepStates((prevStates) => ({ ...prevStates, [key]: "idle" }));
      return false;
    }
  };

  const cancelStep = async (key: ReactivationStepKey) => {
    const runId = stepRunIds[key];
    if (!reviewId || !runId) return;
    try {
      await reviewsApi.cancelRun(reviewId, runId);
      setStepLogs((prevLogs) => ({
        ...prevLogs,
        [key]: [...(prevLogs[key] || []), { type: "warn", msg: "Cancel requested by reviewer" }],
      }));
    } catch (error) {
      setStepLogs((prevLogs) => ({
        ...prevLogs,
        [key]: [
          ...(prevLogs[key] || []),
          {
            type: "err",
            msg: error instanceof Error ? error.message : "Failed to cancel run",
          },
        ],
      }));
    }
  };

  const allDone = REACTIVATION_STEPS.every(
    (reactivationStep) => stepStates[reactivationStep.key] === "done",
  );
  const isRunningAll = REACTIVATION_STEPS.some(
    (reactivationStep) => stepStates[reactivationStep.key] === "loading",
  );

  const runAll = async () => {
    for (const step of REACTIVATION_STEPS) {
      if (stepStates[step.key] === "done") continue;
      const succeeded = await runStep(step.key, stepParams[step.key]);
      if (!succeeded) break;
    }
  };

  const reviewReeFiles = useMemo<ReeFile[]>(
    () =>
      (reviewRootFilesState || []).map((file, index) => ({
        id: `review-file-${index}-${file.path}`,
        name: file.path,
        type: "file",
        tag: "REE",
        size: file.size,
      })),
    [reviewRootFilesState],
  );

  const reviewWorkspaceTree = useMemo<FileTreeNode[]>(
    () => buildTreeFromPaths(reviewWorkspaceFilesState || [], "review-workspace"),
    [reviewWorkspaceFilesState],
  );

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      <header
        style={{
          height: 48,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          position: "sticky",
          top: 0,
          zIndex: 100,
          flexShrink: 0,
          boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 5,
            color: C.textMuted,
            padding: "4px 8px",
            borderRadius: 6,
            transition: "all 0.12s",
          }}
          {...hoverColor(C.textMid, C.textMuted)}
          {...hoverBg(C.surfaceAlt, "transparent")}
        >
          {Ic.arrowLeft()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
        </button>
        <div style={{ width: 1, height: 18, background: C.border }} />
        <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          REE Reviewer
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            background: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: 6,
          }}
        >
          <span style={{ color: "#b45309", display: "flex" }}>{Ic.star(12)}</span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "#92400e",
              fontFamily: F.sans,
              letterSpacing: 0.3,
            }}
          >
            REVIEWER MODE
          </span>
        </div>
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        <aside
          style={{
            width: 256,
            borderRight: `1px solid ${C.border}`,
            background: C.surface,
            overflowY: "auto",
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "14px 16px 12px",
              background: `linear-gradient(160deg, ${levelMeta.bg} 0%, ${C.surface} 100%)`,
              borderBottom: `1px solid ${levelMeta.color}25`,
            }}
          >
            <div
              style={{
                ...S_SECTION_LABEL_SMALL,
                letterSpacing: 1.4,
                color: levelMeta.color,
                marginBottom: 5,
              }}
            >
              Specimen Pod
            </div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: C.text,
                fontFamily: F.mono,
                marginBottom: 8,
                wordBreak: "break-all",
              }}
            >
              {ree.name}
            </div>
            <LevelBadge level={level} />
            <div
              style={{
                marginTop: 10,
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 9px",
                background: "rgba(255,255,255,0.7)",
                border: `1px solid ${levelMeta.color}25`,
                borderRadius: 6,
              }}
            >
              <span style={{ color: levelMeta.color, display: "flex", flexShrink: 0 }}>
                {Ic.lock(10)}
              </span>
              <div>
                <div
                  style={{
                    fontSize: 9,
                    fontWeight: 600,
                    color: levelMeta.color,
                    fontFamily: F.sans,
                  }}
                >
                  Sealed
                </div>
                <div style={{ fontSize: 10, fontFamily: F.mono, color: C.textMid }}>{sealDate}</div>
              </div>
            </div>
          </div>
          <div style={{ padding: "14px 16px", borderBottom: `1px solid ${C.border}` }}>
            <div
              style={{
                ...S_SECTION_LABEL_SMALL,
                marginBottom: 10,
              }}
            >
              Navigation
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <button
                type="button"
                onClick={() => setReviewerPage("review")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  border: `1px solid ${reviewerPage === "review" ? levelMeta.color : C.border}`,
                  borderRadius: 7,
                  background: reviewerPage === "review" ? `${levelMeta.bg}` : C.surface,
                  color: reviewerPage === "review" ? levelMeta.color : C.textMid,
                  fontSize: 12,
                  fontWeight: 600,
                  fontFamily: F.sans,
                  padding: "7px 9px",
                  cursor: "pointer",
                  textAlign: "left",
                }}
                {...hoverBg(
                  C.surfaceAlt,
                  reviewerPage === "review" ? `${levelMeta.bg}` : C.surface,
                )}
              >
                <span style={{ display: "flex" }}>{Ic.shield(13)}</span>
                Review
              </button>
              <button
                type="button"
                onClick={() => setReviewerPage("files")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  border: `1px solid ${reviewerPage === "files" ? levelMeta.color : C.border}`,
                  borderRadius: 7,
                  background: reviewerPage === "files" ? `${levelMeta.bg}` : C.surface,
                  color: reviewerPage === "files" ? levelMeta.color : C.textMid,
                  fontSize: 12,
                  fontWeight: 600,
                  fontFamily: F.sans,
                  padding: "7px 9px",
                  cursor: "pointer",
                  textAlign: "left",
                }}
                {...hoverBg(C.surfaceAlt, reviewerPage === "files" ? `${levelMeta.bg}` : C.surface)}
              >
                <span style={{ display: "flex" }}>{Ic.file(13)}</span>
                Files ({reviewRootFilesState.length + reviewWorkspaceFilesState.length})
              </button>
            </div>
          </div>
          <div style={{ padding: "14px 16px", borderBottom: `1px solid ${C.border}` }}>
            <div
              style={{
                ...S_SECTION_LABEL_SMALL,
                marginBottom: 10,
              }}
            >
              Metadata
            </div>
            <MetaRow label="Origin URL" value={ree.origin_url} mono href={ree.origin_url} />
            <MetaRow label="Runtime" value={ree.runtime} mono color={C.textMid} />
            <MetaRow label="Build Script" value={ree.build_runtime_script} mono color={C.textMid} />
            <MetaRow
              label="Activation Script"
              value={ree.activation_script}
              mono
              color={C.textMid}
            />
            <MetaRow label="SBOM" value={ree.sbom} mono color={C.textMid} />
            {hbomSummaryLines(ree.hardware_description).length > 0 && (
              <div style={{ paddingTop: 8 }}>
                <div
                  style={{
                    ...S_SECTION_LABEL_SMALL,
                    marginBottom: 6,
                  }}
                >
                  Hardware BOM
                </div>
                {hbomSummaryLines(ree.hardware_description).map((line) => (
                  <div
                    key={line}
                    style={{
                      display: "flex",
                      fontSize: 11,
                      marginBottom: 3,
                    }}
                  >
                    <span style={{ fontFamily: F.mono, color: C.textMid }}>{line}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ padding: "14px 16px" }}>
            <div
              style={{
                ...S_SECTION_LABEL_SMALL,
                marginBottom: 12,
              }}
            >
              Provenance
            </div>
            <RvProvenanceChain ree={ree} />
          </div>
        </aside>

        <main
          style={{
            flex: 1,
            overflowY: "auto",
            minWidth: 0,
            background: `linear-gradient(180deg, ${levelMeta.bg}50 0%, ${C.bg} 320px)`,
          }}
        >
          {reviewerPage === "review" ? (
            <>
              <div
                style={{
                  display: "flex",
                  justifyContent: "center",
                  borderBottom: `1px solid ${C.border}`,
                  paddingBottom: 28,
                }}
              >
                <PodOrbitControl
                  level={level}
                  levelMeta={levelMeta}
                  stepStates={stepStates}
                  allDone={allDone}
                  isRunningAll={isRunningAll}
                  onRunAll={runAll}
                />
              </div>
              <div style={{ padding: "20px 28px" }}>
                {allDone && (
                  <div style={{ marginBottom: 20 }}>
                    <RvVerdictBanner allDone={allDone} />
                  </div>
                )}
                <div style={{ maxWidth: 660 }}>
                  {REACTIVATION_STEPS.map((step, i) => {
                    const prevDone =
                      i === 0 || stepStates[REACTIVATION_STEPS[i - 1].key] === "done";
                    return (
                      <RvStepCard
                        key={step.key}
                        step={step}
                        index={i}
                        state={stepStates[step.key] || "idle"}
                        log={stepLogs[step.key] || null}
                        params={stepParams[step.key]}
                        onSetParam={setParam}
                        onRun={runStep}
                        onCancel={cancelStep}
                        isLast={i === REACTIVATION_STEPS.length - 1}
                        prevDone={prevDone}
                      />
                    );
                  })}
                </div>
              </div>
            </>
          ) : (
            <div style={{ padding: "20px 28px" }}>
              <div style={{ maxWidth: 980 }}>
                <PageFiles files={reviewWorkspaceTree} reeFiles={reviewReeFiles} />
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
