import type { AppShellPage } from "@core/app-shell/pages";
import type { AxisKey } from "@core/evaluate/axes";
import type { DependencyEcosystem, DependencyStatus, RuntimePresence } from "@core/evaluate/Threat";
import type { ArchiveRepoKey } from "@core/ree-steps/stepTypes";
import type { ReeRunFailureTone } from "@core/runs/runFailurePresentation";

/** Domain identity → CSS custom property reference.
 *
 * The escape hatch, and deliberately a narrow one. A component that can express
 * itself in CSS should render `data-step={node.key}` and let its module select
 * on it; this file exists for the places that cannot — SVG attributes and the
 * inline styles still awaiting their CSS Module.
 *
 * What it never contains is a visual literal. Every function below returns a
 * `var(--…)` reference to a role declared in `tones.css`, so the values still
 * live in one place and a token rename is still a single edit. The identity
 * types are imported from core, which is what makes a new stage or status a
 * compile error here rather than a silently unstyled element.
 */

/** How strongly a tone is being asked to read. */
type ToneRole = "line" | "ink" | "wash" | "edge";

const reference = (family: string, identity: string, role: ToneRole): string =>
  `var(--${family}-${identity}-${role})`;

/** A pipeline stage, keyed by the page key it already has. */
export const stageTone = (page: AppShellPage, role: ToneRole = "line"): string =>
  reference("stage", page, role);

/** One of the three reproducibility axes. */
export const axisTone = (axis: AxisKey, role: ToneRole = "line"): string =>
  reference("axis", axis, role);

/** A dependency's ecosystem — PyPI, conda, npm, apt, OCI. */
export const ecosystemTone = (ecosystem: DependencyEcosystem, role: ToneRole = "line"): string =>
  reference("eco", ecosystem, role);

/** How tightly a dependency is pinned. */
export const dependencyStatusTone = (status: DependencyStatus, role: ToneRole = "line"): string =>
  reference("dependency", status, role);

/** The SBOM cross-check verdict for a dependency. */
export const presenceTone = (presence: RuntimePresence, role: ToneRole = "line"): string =>
  reference("presence", presence, role);

/** A deposit target — Software Heritage, Zenodo, Dataverse. */
export const archiveTone = (repo: ArchiveRepoKey, role: ToneRole = "line"): string =>
  reference("archive", repo, role);

/** A failed run's class: transient, rejected, or fault. */
export const failureTone = (tone: ReeRunFailureTone): string => reference("failure", tone, "line");

/**
 * A tone at partial opacity, for the tints and glows that used to be written as
 * `${color}40` — appending alpha text to a `var(--…)` reference produces an
 * invalid value that fails silently, so the alpha is composed instead.
 *
 * `percent` is the opacity the old two-digit hex suffix stood for: `40` is
 * 64/255, so `translucent(tone, 25)`.
 */
export const translucent = (tone: string, percent: number): string =>
  `color-mix(in srgb, ${tone} ${percent}%, transparent)`;
