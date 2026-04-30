import { useEffect, useMemo, useState } from "react";
import type { ReviewRepository } from "../../application/ports/ReviewRepository";
import type {
  Level,
  StepState,
  WorkflowParamValue,
} from "../../application/workflow/WorkflowStepTypes";
import { createEmptyRee, type Ree } from "../../domain/ree/ReeSpec";
import type { LogLine, ReeFile } from "../../domain/ree/ReeTypes";
import { LEVELS } from "../../domain/review/levels";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { C } from "../theme/theme";
import { ReviewerContent } from "./components/ReviewerContent";
import { ReviewerHeader } from "./components/ReviewerHeader";
import { ReviewerSidebar } from "./components/ReviewerSidebar";
import { buildTreeFromPaths } from "./components/reviewerFileTree";
import {
  REACTIVATION_STEPS,
  type ReactivationParams,
  type ReactivationStepKey,
} from "./reviewerSupport";

interface ReviewerViewProps {
  reviewId?: string;
  ree?: Ree;
  reviewFiles?: Array<{ path: string; size?: number }>;
  reviewWorkspaceFiles?: Array<{ path: string; size?: number }>;
  onBack: () => void;
  reviewRepository: ReviewRepository;
  PodOrbitControl: React.ComponentType<{
    level: number;
    levelMeta: Level;
    stepStates: Record<string, StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

export function ReviewerView({
  reviewId,
  ree: reeInput,
  reviewFiles = [],
  reviewWorkspaceFiles = [],
  onBack,
  reviewRepository,
  PodOrbitControl,
}: ReviewerViewProps) {
  const ree = reeInput || createEmptyRee();
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

  useEffect(() => {
    setReviewRootFilesState(reviewFiles);
  }, [reviewFiles]);

  useEffect(() => {
    setReviewWorkspaceFilesState(reviewWorkspaceFiles);
  }, [reviewWorkspaceFiles]);

  const refreshReviewFiles = async () => {
    if (!reviewId) return;
    const detail = await reviewRepository.getReview(reviewId);
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

  const setParam = (stepKey: ReactivationStepKey, paramKey: string, value: WorkflowParamValue) =>
    setStepParams((current) => ({
      ...current,
      [stepKey]: { ...current[stepKey], [paramKey]: value },
    }));

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
  const isTerminalStatus = (status: string) =>
    status === "succeeded" || status === "failed" || status === "canceled";

  const runBackendStep = async (key: ReactivationStepKey): Promise<LogLine[]> => {
    if (!reviewId) {
      const localStep = REACTIVATION_STEPS.find((step) => step.key === key);
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
      runId = (await reviewRepository.acquireSource(reviewId)).runId;
    } else if (key === "build_runtime") {
      runId = (
        await reviewRepository.createBuildRuntimeRun(reviewId, {
          build_runtime_script_path: ree.build_runtime_script,
          produced_runtime_path: ree.runtime,
        })
      ).runId;
    } else {
      runId = (
        await reviewRepository.createActivationTestRun(reviewId, {
          activation_script_path: ree.activation_script,
        })
      ).runId;
    }
    setStepRunIds((current) => ({ ...current, [key]: runId }));

    const collected: LogLine[] = [];
    const seen = new Set<string>();
    let cursor: string | undefined;

    for (let index = 0; index < 120; index += 1) {
      const logs = await reviewRepository.listRunLogs(reviewId, runId, cursor);
      for (const line of logs.lines) {
        const dedupeKey = `${line.ts || ""}::${line.type}::${line.msg}`;
        if (seen.has(dedupeKey)) continue;
        seen.add(dedupeKey);
        collected.push(line);
      }
      cursor = logs.nextCursor;
      setStepLogs((current) => ({ ...current, [key]: [...collected] }));

      if (isTerminalStatus((await reviewRepository.getRun(reviewId, runId)).status)) {
        while (logs.hasMore && cursor) {
          const nextLogs = await reviewRepository.listRunLogs(reviewId, runId, cursor);
          for (const line of nextLogs.lines) {
            const dedupeKey = `${line.ts || ""}::${line.type}::${line.msg}`;
            if (seen.has(dedupeKey)) continue;
            seen.add(dedupeKey);
            collected.push(line);
          }
          cursor = nextLogs.nextCursor;
        }
        const run = await reviewRepository.getRun(reviewId, runId);
        if (run.status === "canceled") {
          collected.push({ type: "warn", msg: "Run canceled" });
        } else if (run.status !== "succeeded") {
          collected.push({ type: "err", msg: `Run ended with status: ${run.status}` });
        }
        setStepRunIds((current) => ({ ...current, [key]: "" }));
        return collected;
      }

      await sleep(index < 10 ? 700 : index < 40 ? 1200 : 2000);
    }

    collected.push({ type: "warn", msg: "Run polling timed out before completion" });
    setStepRunIds((current) => ({ ...current, [key]: "" }));
    return collected;
  };

  const runStep = async (key: ReactivationStepKey, params: ReactivationParams) => {
    void params;
    if (!REACTIVATION_STEPS.find((step) => step.key === key)) return false;
    setStepStates((current) => ({ ...current, [key]: "loading" }));
    setStepLogs((current) => ({ ...current, [key]: [] }));
    try {
      const lines = await runBackendStep(key);
      setStepLogs((current) => ({ ...current, [key]: lines }));
      const hasError = lines.some((line) => line.type === "err");
      setStepStates((current) => ({ ...current, [key]: hasError ? "idle" : "done" }));
      if (!hasError) {
        try {
          await refreshReviewFiles();
        } catch {
          setStepLogs((current) => ({
            ...current,
            [key]: [
              ...(current[key] || []),
              { type: "warn", msg: "Run succeeded, but failed to refresh file list" },
            ],
          }));
        }
      }
      return !hasError;
    } catch (error) {
      setStepLogs((current) => ({
        ...current,
        [key]: [
          { type: "err", msg: error instanceof Error ? error.message : "Failed to execute step" },
        ],
      }));
      setStepStates((current) => ({ ...current, [key]: "idle" }));
      return false;
    }
  };

  const cancelStep = async (key: ReactivationStepKey) => {
    const runId = stepRunIds[key];
    if (!reviewId || !runId) return;
    try {
      await reviewRepository.cancelRun(reviewId, runId);
      setStepLogs((current) => ({
        ...current,
        [key]: [...(current[key] || []), { type: "warn", msg: "Cancel requested by reviewer" }],
      }));
    } catch (error) {
      setStepLogs((current) => ({
        ...current,
        [key]: [
          ...(current[key] || []),
          { type: "err", msg: error instanceof Error ? error.message : "Failed to cancel run" },
        ],
      }));
    }
  };

  const allDone = REACTIVATION_STEPS.every((step) => stepStates[step.key] === "done");
  const isRunningAll = REACTIVATION_STEPS.some((step) => stepStates[step.key] === "loading");

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
      <ReviewerHeader title={ree.name || "untitled"} onBack={onBack} />
      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
        <ReviewerSidebar
          ree={ree}
          level={level}
          levelMeta={levelMeta}
          sealDate={sealDate}
          reviewerPage={reviewerPage}
          fileCount={reviewRootFilesState.length + reviewWorkspaceFilesState.length}
          setReviewerPage={setReviewerPage}
        />
        <ReviewerContent
          reviewerPage={reviewerPage}
          level={level}
          levelMeta={levelMeta}
          stepStates={stepStates}
          stepLogs={stepLogs}
          stepParams={stepParams}
          allDone={allDone}
          isRunningAll={isRunningAll}
          runAll={runAll}
          setParam={setParam}
          runStep={runStep}
          cancelStep={cancelStep}
          reviewWorkspaceTree={reviewWorkspaceTree}
          reviewReeFiles={reviewReeFiles}
          PodOrbitControl={PodOrbitControl}
        />
      </div>
    </div>
  );
}
