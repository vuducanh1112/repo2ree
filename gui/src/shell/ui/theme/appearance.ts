import type { AppShellPage } from "@core/app-shell/pages";
import type { AxisKey } from "@core/evaluate/axes";
import type { DependencyEcosystem, DependencyStatus } from "@core/evaluate/Threat";
import type { ArchiveRepoKey } from "@core/ree-steps/stepTypes";
import type { ReeRunFailureTone } from "@core/runs/runFailurePresentation";

type StageToneRole = "line" | "ink" | "wash";
type AxisToneRole = "line" | "ink";
type ArchiveToneRole = "line" | "ink";
type EcosystemToneRole = "line" | "wash";
type DependencyToneRole = "line" | "wash" | "edge";
type ToneRole = StageToneRole | DependencyToneRole;

const reference = (family: string, identity: string, role: ToneRole): string =>
  `var(--${family}-${identity}-${role})`;

export const stageTone = (page: AppShellPage, role: StageToneRole = "line"): string =>
  reference("stage", page, role);

export const axisTone = (axis: AxisKey, role: AxisToneRole = "line"): string =>
  reference("axis", axis, role);

export const ecosystemTone = (
  ecosystem: DependencyEcosystem,
  role: EcosystemToneRole = "line",
): string => reference("eco", ecosystem, role);

export const dependencyStatusTone = (
  status: DependencyStatus,
  role: DependencyToneRole = "line",
): string => reference("dependency", status, role);

export const archiveTone = (repo: ArchiveRepoKey, role: ArchiveToneRole = "line"): string =>
  reference("archive", repo, role);

export const failureTone = (tone: ReeRunFailureTone): string => reference("failure", tone, "line");

export const translucent = (tone: string, percent: number): string =>
  `color-mix(in srgb, ${tone} ${percent}%, transparent)`;
