import { createEmptyReeSpec } from "../../../core/ree/ReeSpec";
import type { ReeFile } from "../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import { buildTreeFromPaths } from "./components/reviewerFileTree";
import {
  REACTIVATION_STEPS,
  type ReactivationParams,
  type ReactivationStepKey,
} from "./reviewerSupport";

export function resolveReviewerRee(reeInput?: ReeEditorViewModel): ReeEditorViewModel {
  return (
    reeInput || {
      ...createEmptyReeSpec(),
      dependencyLevel: 0,
      environmentLevel: 0,
      machineLevel: 0,
      runtimeIncluded: false,
    }
  );
}

export function formatSealDate(sealedAt?: string): string {
  return sealedAt
    ? new Date(sealedAt).toLocaleString([], {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "unknown";
}

export function initReactivationParams(): Record<ReactivationStepKey, ReactivationParams> {
  return Object.fromEntries(
    REACTIVATION_STEPS.map((step) => [
      step.key,
      Object.fromEntries((step.params || []).map((param) => [param.key, param.default])),
    ]),
  ) as Record<ReactivationStepKey, ReactivationParams>;
}

export const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const isTerminalStatus = (status: string) =>
  status === "succeeded" || status === "failed" || status === "canceled";

export function mapReviewReeFiles(
  reviewRootFilesState: Array<{ path: string; size?: number }>,
): ReeFile[] {
  return (reviewRootFilesState || []).map((file, index) => ({
    id: `review-file-${index}-${file.path}`,
    name: file.path,
    type: "file",
    tag: "REE",
    size: file.size,
  }));
}

export function mapReviewWorkspaceTree(
  reviewWorkspaceFilesState: Array<{ path: string; size?: number }>,
): FileTreeNode[] {
  return buildTreeFromPaths(reviewWorkspaceFilesState || [], "review-workspace");
}
