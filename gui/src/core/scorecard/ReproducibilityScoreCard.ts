// The reproducibility scorecard: five evidence categories plus one ordinal
// level (R0..R5), computed by the backend purely from the REE's persisted
// record (intent + session + run receipts) — see the core module
// `reproducibility_scorecard.py` for the ladder's normative choices. The
// GUI only renders it; nothing here derives new facts.

export type ScoreCardCategoryKey = "source" | "runtime" | "activation" | "experiments" | "results";

export interface ScoreCardRung {
  key: string;
  label: string;
  reached: boolean;
  detail: string;
  /** Fraction for rungs aggregated over the experiment list; null elsewhere. */
  done: number | null;
  total: number | null;
}

export interface ScoreCardCategory {
  key: ScoreCardCategoryKey;
  label: string;
  rungs: ScoreCardRung[];
}

export interface ReproducibilityScoreCard {
  level: number;
  levelCode: string;
  levelName: string;
  sealed: boolean;
  categories: ScoreCardCategory[];
}

const CATEGORY_KEYS: readonly ScoreCardCategoryKey[] = [
  "source",
  "runtime",
  "activation",
  "experiments",
  "results",
];

// Per-category accent, matched to the canvas node that owns the evidence
// (source/amber, runtime/cyan, activation/violet, experiments/indigo,
// results–archive/orange) so the scorecard reads as the ring, condensed.
export const SCORECARD_CATEGORY_COLORS: Record<ScoreCardCategoryKey, string> = {
  source: "#f59e0b",
  runtime: "#0891b2",
  activation: "#7c3aed",
  experiments: "#4f46e5",
  results: "#e4572e",
};

// Light companion tints for chrome that needs a soft fill (cable cores etc.).
const CATEGORY_BG: Record<ScoreCardCategoryKey, string> = {
  source: "#fef3c7",
  runtime: "#cffafe",
  activation: "#ede9fe",
  experiments: "#e0e7ff",
  results: "#ffedd5",
};

// The category whose predicate gates the *next* level — what a chrome accent
// should point at. Index == current level; R5 has nothing left to gate.
const LEVEL_BLOCKING_CATEGORY: readonly (ScoreCardCategoryKey | null)[] = [
  "source",
  "runtime",
  "activation",
  "experiments",
  "results",
  null,
];

const DONE_STANDING = { color: "#10b981", bg: "#d1fae5" };

interface ScoreCardStanding {
  color: string;
  bg: string;
  label: string;
}

/** A single {color,bg,label} descriptor for chrome with room for one accent:
 * tinted by the category currently gating the next level, labelled with the
 * ordinal level. Falls back to the R0 default card when none is loaded yet. */
export function scoreCardStanding(card: ReproducibilityScoreCard | null): ScoreCardStanding {
  const resolved = card ?? emptyReproducibilityScoreCard();
  const blocking = LEVEL_BLOCKING_CATEGORY[resolved.level] ?? null;
  const tint = blocking
    ? { color: SCORECARD_CATEGORY_COLORS[blocking], bg: CATEGORY_BG[blocking] }
    : DONE_STANDING;
  return { ...tint, label: `${resolved.levelCode} · ${resolved.levelName}` };
}

function rung(key: string, label: string, fraction = false): ScoreCardRung {
  return {
    key,
    label,
    reached: false,
    detail: "",
    done: fraction ? 0 : null,
    total: fraction ? 0 : null,
  };
}

/**
 * The scorecard of an empty record — level R0 with every rung unreached.
 * Mirrors what the backend derives from a freshly initialised REE, so the UI
 * can show the true "lowest level" default instead of an absence state while
 * no server card is available yet. Pure.
 */
export function emptyReproducibilityScoreCard(): ReproducibilityScoreCard {
  return {
    level: 0,
    levelCode: "R0",
    levelName: "Draft",
    sealed: false,
    categories: [
      {
        key: "source",
        label: "Source",
        rungs: [
          rung("linked", "Linked"),
          rung("acquired", "Acquired"),
          rung("archived", "SWH-archived"),
          rung("included", "Included"),
        ],
      },
      {
        key: "runtime",
        label: "Runtime",
        rungs: [
          rung("available", "Available"),
          rung("built", "Built"),
          rung("inventoried", "SBOM"),
          rung("included", "Included"),
        ],
      },
      { key: "activation", label: "Activation", rungs: [rung("passed", "Passed")] },
      {
        key: "experiments",
        label: "Experiments",
        rungs: [rung("validated", "Validated", true)],
      },
      {
        key: "results",
        label: "Results",
        rungs: [rung("captured", "Captured", true), rung("included", "Included")],
      },
    ],
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function parseRung(value: unknown): ScoreCardRung | null {
  const raw = asRecord(value);
  if (!raw || typeof raw.key !== "string" || typeof raw.label !== "string") return null;
  return {
    key: raw.key,
    label: raw.label,
    reached: raw.reached === true,
    detail: typeof raw.detail === "string" ? raw.detail : "",
    done: typeof raw.done === "number" ? raw.done : null,
    total: typeof raw.total === "number" ? raw.total : null,
  };
}

function parseCategory(value: unknown): ScoreCardCategory | null {
  const raw = asRecord(value);
  if (!raw || typeof raw.label !== "string") return null;
  const key = CATEGORY_KEYS.find((candidate) => candidate === raw.key);
  if (!key) return null;
  const rungs = Array.isArray(raw.rungs)
    ? raw.rungs.map(parseRung).filter((rung): rung is ScoreCardRung => rung !== null)
    : [];
  return { key, label: raw.label, rungs };
}

/**
 * Defensively parse a raw scorecard payload (e.g. from the API) into a typed
 * scorecard. Returns null when the payload is not a usable scorecard. Pure.
 */
export function parseReproducibilityScoreCard(value: unknown): ReproducibilityScoreCard | null {
  const raw = asRecord(value);
  if (!raw || typeof raw.level !== "number") return null;
  const categories = Array.isArray(raw.categories)
    ? raw.categories
        .map(parseCategory)
        .filter((category): category is ScoreCardCategory => category !== null)
    : [];
  return {
    level: Math.trunc(raw.level),
    levelCode: typeof raw.level_code === "string" ? raw.level_code : `R${Math.trunc(raw.level)}`,
    levelName: typeof raw.level_name === "string" ? raw.level_name : "",
    sealed: raw.sealed === true,
    categories,
  };
}
