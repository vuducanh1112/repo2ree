// Theme for the glass "pages" surfaces — the bright, frosted page views
// (archive, build-runtime, evaluate, experiments, files, hardware-bom,
// metadata, seal, source). This is intentionally
// a separate palette from the canvas/chrome tokens in ./tokens (C): the two
// share only the font primitives (F) imported below. Keep the colors distinct.
import type { FileTypeCategory } from "@core/workspace/PathUtils";
import type React from "react";
import { S_ACTION_BUTTON_BASE } from "./stylesCore";
import { F } from "./tokens";

type ActionTone = "neutral" | "primary" | "danger" | "success";

export const lgColors = {
  blue: "#0ea5e9",
  indigo: "#4f46e5",
  cyan: "#0891b2",
  violet: "#7c3aed",
  text: "#0f172a",
  textMid: "#475569",
  textMuted: "#64748b",
  required: "#fb7185",
  danger: "#be123c",
  dangerBorder: "rgba(251, 113, 133, 0.4)",
  success: "#047857",
  warning: "#a16207",
  accent: "#0369a1",
  primaryDeep: "#0c4a6e",
  suggestionText: "#3730a3",
  chipText: "#1d4ed8",
  white: "#fff",
} as const;

export const lgPageColors = {
  runtimeEnv: lgColors.cyan,
  files: lgColors.indigo,
} as const;

const lgBorders = {
  panel: "1px solid rgba(125, 211, 252, 0.58)",
  frame: "1px solid rgba(125, 211, 252, 0.48)",
  section: "1px solid rgba(125, 211, 252, 0.42)",
  sectionStrong: "1px solid rgba(14, 165, 233, 0.28)",
  row: "1px solid rgba(148, 163, 184, 0.3)",
  rowSoft: "1px solid rgba(148, 163, 184, 0.34)",
  input: "rgba(95, 142, 190, 0.42)",
  inputActive: "rgba(56, 189, 248, 0.86)",
  progress: "1px solid rgba(125, 211, 252, 0.36)",
  success: "1px solid rgba(34, 197, 94, 0.36)",
  successStrong: "1px solid rgba(34, 197, 94, 0.42)",
  warning: "1px solid rgba(245, 158, 11, 0.45)",
  chip: "1px solid rgba(79, 70, 229, 0.28)",
  suggestion: "1px solid rgba(79, 70, 229, 0.24)",
  actionPrimary: "1px solid rgba(14, 165, 233, 0.35)",
  actionNeutral: "1px solid rgba(148, 163, 184, 0.34)",
  iconButton: "1px solid rgba(148, 163, 184, 0.35)",
} as const;

export const lgBackgrounds = {
  page: "radial-gradient(circle at 80% 8%, rgba(14, 165, 233, 0.18), transparent 28%), radial-gradient(circle at 12% 18%, rgba(99, 102, 241, 0.12), transparent 24%), linear-gradient(135deg, #f8fbff 0%, #eef8ff 48%, #ffffff 100%)",
  frameGrid:
    "linear-gradient(rgba(14, 165, 233, 0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(14, 165, 233, 0.06) 1px, transparent 1px)",
  panel:
    "linear-gradient(145deg, rgba(255, 255, 255, 0.82), rgba(240, 249, 255, 0.7) 52%, rgba(255, 255, 255, 0.76))",
  glass: "rgba(255, 255, 255, 0.54)",
  glassStrong: "rgba(255, 255, 255, 0.72)",
  row: "rgba(248, 250, 252, 0.8)",
  frame: "rgba(255, 255, 255, 0.38)",
  input: "rgba(255, 255, 255, 0.72)",
  disabled: "rgba(241, 245, 249, 0.72)",
  readout: "rgba(255, 255, 255, 0.56)",
  footer: "rgba(248, 250, 252, 0.66)",
  icon: "rgba(240, 249, 255, 0.88)",
  iconSoft: "rgba(240, 249, 255, 0.72)",
  chip: "rgba(239, 246, 255, 0.82)",
  primary: "rgba(239, 246, 255, 0.88)",
  suggestion: "rgba(248, 250, 252, 0.88)",
  danger: "rgba(255, 241, 242, 0.82)",
  success: "rgba(240, 253, 244, 0.78)",
  successStrong: "rgba(220, 252, 231, 0.86)",
  ready: "rgba(220, 252, 231, 0.78)",
  draft: "rgba(254, 249, 195, 0.82)",
  progressTrack: "rgba(226, 232, 240, 0.76)",
  next: `linear-gradient(135deg, ${lgColors.blue}, ${lgColors.indigo})`,
  progress: `linear-gradient(90deg, ${lgColors.cyan}, ${lgColors.indigo})`,
  selectChevron:
    "linear-gradient(45deg, transparent 50%, #334155 50%), linear-gradient(135deg, #334155 50%, transparent 50%)",
} as const;

// Identity helper: the constraint contextually types each member as
// React.CSSProperties (so literals like flexDirection: "column" are preserved
// rather than widened to string), while T keeps the specific keys for safety.
const styleSheet = <T extends Record<string, React.CSSProperties>>(s: T): T => s;

// Shared layout/background for the `footer` and `footerBar` styles below; only
// their border/padding differ.
const S_FOOTER_BASE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  justifyContent: "space-between",
  background: lgBackgrounds.footer,
  flexWrap: "wrap",
};

export const lgStyles = styleSheet({
  panel: {
    border: lgBorders.panel,
    borderRadius: 12,
    background: lgBackgrounds.panel,
    boxShadow: "0 24px 70px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.88)",
    backdropFilter: "blur(18px)",
  },
  fieldFrame: {
    display: "flex",
    flexDirection: "column",
    gap: 7,
    minWidth: 0,
  },
  label: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 700,
    color: lgColors.text,
    fontFamily: F.sans,
  },
  helper: {
    fontSize: 11,
    color: lgColors.textMuted,
    lineHeight: 1.4,
    fontFamily: F.sans,
  },
  pageRoot: {
    height: "100%",
    minHeight: 0,
    overflow: "auto",
    padding: 24,
    color: lgColors.text,
    background: lgBackgrounds.page,
    fontFamily: F.sans,
  },
  pageFrame: {
    minHeight: "100%",
    border: lgBorders.frame,
    borderRadius: 14,
    backgroundImage: lgBackgrounds.frameGrid,
    backgroundSize: "22px 22px",
    backgroundColor: lgBackgrounds.frame,
    boxShadow: "inset 0 0 80px rgba(14, 165, 233, 0.07)",
    padding: 22,
  },
  pageHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 18,
    borderBottom: "1px solid rgba(125, 211, 252, 0.44)",
    paddingBottom: 20,
    marginBottom: 22,
  },
  headerIcon: {
    width: 48,
    height: 48,
    borderRadius: 13,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: lgColors.cyan,
    background: lgBackgrounds.icon,
    border: "1px solid rgba(14, 165, 233, 0.32)",
    boxShadow: "0 14px 30px rgba(14, 165, 233, 0.16)",
    flexShrink: 0,
  },
  title: {
    margin: 0,
    color: lgColors.text,
    fontSize: 21,
    lineHeight: 1.2,
    fontWeight: 800,
  },
  subtitle: {
    margin: 0,
    color: lgColors.textMid,
    fontSize: 13,
    lineHeight: 1.45,
  },
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "minmax(320px, 1fr) minmax(260px, 340px)",
    gap: 18,
    alignItems: "start",
  },
  sectionBody: {
    padding: 22,
  },
  sectionHeader: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 22,
  },
  sectionIcon: {
    width: 34,
    height: 34,
    borderRadius: 9,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: lgColors.blue,
    border: lgBorders.sectionStrong,
    background: lgBackgrounds.iconSoft,
  },
  sectionTitle: {
    margin: 0,
    fontSize: 18,
    color: lgColors.text,
  },
  sectionSubtitle: {
    color: lgColors.textMuted,
    fontSize: 12,
  },
  // An inset card for a single section, raised slightly off the main glass panel
  // so each major section reads as its own bounded subpanel rather than blending
  // into one continuous surface.
  subPanel: {
    border: lgBorders.section,
    borderRadius: 10,
    background: lgBackgrounds.glassStrong,
    boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.8)",
    padding: 18,
  },
  fieldsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: 18,
  },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    border: lgBorders.chip,
    borderRadius: 6,
    padding: "5px 8px",
    color: lgColors.chipText,
    background: lgBackgrounds.chip,
    fontSize: 12,
    fontFamily: F.sans,
    maxWidth: "100%",
  },
  chipRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 10,
  },
  inlineChipWrap: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  },
  iconRemoveSmall: {
    ...S_ACTION_BUTTON_BASE,
    width: 22,
    height: 22,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 999,
    border: lgBorders.iconButton,
    background: lgBackgrounds.glassStrong,
    color: lgColors.textMid,
    cursor: "pointer",
    padding: 0,
  },
  keywordControls: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  flexWrapRow: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  suggestionWrap: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  // `footer` welds to the bottom of a single panel (top border only); `footerBar`
  // is the standalone variant for pages split into separate subpanels (fully
  // bordered, rounded bar). Both share the same layout/background base.
  footer: {
    ...S_FOOTER_BASE,
    borderTop: "1px solid rgba(125, 211, 252, 0.38)",
    padding: "14px 22px",
  },
  footerBar: {
    ...S_FOOTER_BASE,
    border: lgBorders.section,
    borderRadius: 10,
    padding: "12px 18px",
  },
  aside: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  summaryBox: {
    border: lgBorders.section,
    borderRadius: 9,
    padding: 14,
    background: lgBackgrounds.readout,
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  asideHeader: {
    display: "flex",
    justifyContent: "space-between",
    gap: 10,
  },
  asideLabel: {
    color: lgColors.accent,
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  readinessHeader: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 700,
    color: lgColors.text,
    fontFamily: F.sans,
    justifyContent: "space-between",
    marginBottom: 10,
  },
  progressTrack: {
    height: 8,
    borderRadius: 99,
    background: lgBackgrounds.progressTrack,
    overflow: "hidden",
    border: lgBorders.progress,
  },
  progressFill: {
    height: "100%",
    borderRadius: 99,
    background: lgBackgrounds.progress,
    boxShadow: "0 0 16px rgba(14, 165, 233, 0.28)",
    transition: "width 0.25s ease",
  },
  statGrid: {
    marginTop: 12,
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
  },
  statReadout: {
    display: "flex",
    minHeight: 62,
    flexDirection: "column",
    alignItems: "flex-start",
  },
  contributorList: {
    display: "grid",
    gap: 8,
    marginBottom: 10,
  },
  contributorCard: {
    border: lgBorders.row,
    borderRadius: 8,
    padding: "8px 10px",
    background: lgBackgrounds.row,
  },
  contributorHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 8,
  },
  contributorFieldsGrid: {
    display: "grid",
    gap: 8,
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  },
  contributorAddGrid: {
    display: "grid",
    gap: 8,
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  },
  contributorActions: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
    marginTop: 10,
    justifyContent: "flex-end",
  },
  glassPanel: {
    border: lgBorders.panel,
    borderRadius: 10,
    background: lgBackgrounds.glass,
    backdropFilter: "blur(14px)",
    boxShadow: "0 12px 32px rgba(15, 23, 42, 0.09), inset 0 1px 0 rgba(255, 255, 255, 0.85)",
    overflow: "hidden",
  },
});

export function lgInput(locked: boolean, active = false): React.CSSProperties {
  return {
    width: "100%",
    border: `1px solid ${active ? lgBorders.inputActive : lgBorders.input}`,
    borderRadius: 8,
    padding: "12px 13px",
    minHeight: 42,
    fontSize: 14,
    fontFamily: F.sans,
    color: locked ? lgColors.textMuted : lgColors.text,
    background: locked ? lgBackgrounds.disabled : lgBackgrounds.input,
    boxShadow: active
      ? "0 0 0 3px rgba(14, 165, 233, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.92)"
      : "inset 0 1px 0 rgba(255, 255, 255, 0.92)",
    outline: "none",
    transition: "border-color 0.15s, box-shadow 0.15s, background 0.15s",
  };
}

export function lgActionButton(tone: ActionTone, disabled = false): React.CSSProperties {
  const tones = {
    neutral: {
      border: "rgba(148, 163, 184, 0.34)",
      background: lgBackgrounds.glassStrong,
      color: lgColors.textMid,
    },
    primary: {
      border: "rgba(14, 165, 233, 0.35)",
      background: lgBackgrounds.primary,
      color: lgColors.primaryDeep,
    },
    danger: {
      border: "rgba(251, 113, 133, 0.4)",
      background: lgBackgrounds.danger,
      color: lgColors.danger,
    },
    success: {
      border: "rgba(34, 197, 94, 0.36)",
      background: lgBackgrounds.success,
      color: lgColors.success,
    },
  }[tone];

  return {
    ...S_ACTION_BUTTON_BASE,
    width: 28,
    height: 28,
    padding: 0,
    border: `1px solid ${tones.border}`,
    borderRadius: 8,
    background: disabled ? lgBackgrounds.disabled : tones.background,
    color: disabled ? lgColors.textMuted : tones.color,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: disabled ? "not-allowed" : "pointer",
    flexShrink: 0,
  };
}

export function pageIconTint(color: string): { color: string; border: string; shadow: string } {
  return { color, border: `${color}55`, shadow: `${color}28` };
}

export const lgPageRoot: React.CSSProperties = {
  height: "100%",
  minHeight: 0,
  overflow: "auto",
  padding: "46px 36px 32px",
  color: lgColors.text,
};

export function lgStatusBadge(ready: boolean): React.CSSProperties {
  return {
    border: ready ? lgBorders.successStrong : lgBorders.warning,
    borderRadius: 99,
    padding: "3px 8px",
    color: ready ? lgColors.success : lgColors.warning,
    background: ready ? lgBackgrounds.ready : lgBackgrounds.draft,
    fontSize: 11,
    fontWeight: 700,
  };
}

export function lgOutcomeBadge(color: string, bg: string): React.CSSProperties {
  return {
    fontSize: 11,
    fontWeight: 700,
    color,
    background: bg,
    border: `1px solid ${color}40`,
    borderRadius: 99,
    padding: "3px 9px",
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
  };
}

export function lgCorrespondingBadge(): React.CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    border: lgBorders.success,
    borderRadius: 999,
    background: lgBackgrounds.successStrong,
    color: lgColors.success,
    padding: "3px 8px",
    fontSize: 11,
    fontWeight: 700,
    flexShrink: 0,
  };
}

// Forward-navigation ("Next: …") is intentionally a tier below the page's
// primary operation: a tinted, bordered button rather than the gradient +
// glow reserved for lgPrimaryActionButton (Run / Commit). This keeps a single
// loudest call-to-action per page instead of two competing gradient buttons.
export function lgNextButton(): React.CSSProperties {
  return {
    ...S_ACTION_BUTTON_BASE,
    border: lgBorders.actionPrimary,
    borderRadius: 8,
    padding: "10px 18px",
    color: lgColors.primaryDeep,
    background: lgBackgrounds.primary,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    gap: 8,
    cursor: "pointer",
    boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.7)",
  };
}

export function lgGlassButton(): React.CSSProperties {
  return {
    ...S_ACTION_BUTTON_BASE,
    border: lgBorders.actionPrimary,
    background: lgBackgrounds.primary,
    color: lgColors.primaryDeep,
    borderRadius: 8,
    padding: "9px 14px",
    fontWeight: 700,
    cursor: "pointer",
  };
}

export function lgPrimaryActionButton(disabled = false): React.CSSProperties {
  return {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    border: disabled ? lgBorders.actionNeutral : "1px solid rgba(14, 165, 233, 0.42)",
    background: disabled ? lgBackgrounds.disabled : lgBackgrounds.next,
    color: disabled ? lgColors.textMuted : lgColors.white,
    padding: "10px 18px",
    borderRadius: 8,
    fontWeight: 800,
    fontSize: 12,
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: F.sans,
    boxShadow: disabled ? "none" : "0 12px 24px rgba(14, 165, 233, 0.22)",
  };
}

// Solid accent-coloured run button (SBOM, Hardware BOM). Identical shape to the
// primary action, but tinted with a page-specific accent rather than the shared
// blue, so each hub action keeps its own colour identity.
export function lgAccentActionButton(accent: string, disabled = false): React.CSSProperties {
  return {
    ...S_ACTION_BUTTON_BASE,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 16px",
    borderRadius: 8,
    fontSize: 12,
    fontWeight: 800,
    letterSpacing: 0.3,
    cursor: disabled ? "not-allowed" : "pointer",
    color: lgColors.white,
    background: accent,
    border: `1px solid ${accent}`,
    boxShadow: `0 12px 24px ${accent}40`,
    opacity: disabled ? 0.55 : 1,
  };
}

type LgBannerTone = "success" | "danger" | "muted";

export function lgInfoBanner(tone: LgBannerTone): React.CSSProperties {
  const palette = {
    success: { border: "rgba(34, 197, 94, 0.32)", background: lgBackgrounds.success },
    danger: { border: "rgba(251, 113, 133, 0.4)", background: lgBackgrounds.danger },
    muted: { border: "rgba(148, 163, 184, 0.34)", background: lgBackgrounds.glassStrong },
  }[tone];
  return {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 14px",
    borderRadius: 8,
    border: `1px solid ${palette.border}`,
    background: palette.background,
    flexWrap: "wrap",
    fontFamily: F.sans,
  };
}

export function lgPillChip(active: boolean): React.CSSProperties {
  return {
    fontSize: 11,
    fontWeight: 700,
    color: active ? lgColors.chipText : lgColors.textMuted,
    background: active ? lgBackgrounds.chip : lgBackgrounds.disabled,
    border: active ? lgBorders.chip : lgBorders.actionNeutral,
    borderRadius: 99,
    padding: "3px 9px",
    fontFamily: F.sans,
  };
}

export function lgContentCard(marginTop = 12): React.CSSProperties {
  return {
    marginTop,
    border: lgBorders.section,
    borderRadius: 8,
    background: lgBackgrounds.glass,
    padding: 12,
  };
}

export function lgSuggestionButton(): React.CSSProperties {
  return {
    ...S_ACTION_BUTTON_BASE,
    border: lgBorders.suggestion,
    background: lgBackgrounds.suggestion,
    color: lgColors.suggestionText,
    borderRadius: 999,
    padding: "5px 10px",
    fontSize: 12,
    cursor: "pointer",
  };
}

// File-browser surfaces. The tree pane and viewer are translucent glass
// floating over the page's gradient backdrop.
export const lgTree = {
  pane: {
    background: "rgba(255, 255, 255, 0.55)",
    borderColor: "rgba(125, 211, 252, 0.42)",
  },
  sectionBg: "rgba(248, 250, 252, 0.86)",
  selectedBg: "rgba(224, 242, 254, 0.92)",
  selectedText: lgColors.primaryDeep,
  selectedBorder: "rgba(14, 165, 233, 0.5)",
  hoverBg: "rgba(239, 246, 255, 0.7)",
  highlightBg: lgBackgrounds.draft,
  highlightBorder: "rgba(245, 158, 11, 0.45)",
  highlightText: lgColors.warning,
  viewerBg: "rgba(248, 250, 252, 0.62)",
  viewerHeaderBg: lgBackgrounds.glassStrong,
  chipBg: lgBackgrounds.glassStrong,
  inputBg: lgBackgrounds.input,
  calloutBg: "rgba(255, 255, 255, 0.6)",
} as const;

// Tints for the file viewer's lightweight Dockerfile/shell syntax highlighter.
export const lgSyntax = {
  lineNumber: "rgba(148, 163, 184, 0.85)",
  comment: "#94a3b8",
  keyword: lgColors.accent,
  command: "#15803d",
  string: "#b45309",
} as const;

// Presentational tint per coarse file category (see classifyFileType).
export function lgFileTypeColor(category: FileTypeCategory): string {
  return {
    code: lgColors.blue,
    data: lgColors.indigo,
    doc: lgColors.textMid,
    container: lgColors.cyan,
    archive: lgColors.violet,
    binary: lgColors.textMuted,
  }[category];
}

// ── Stage tints ──────────────────────────────────────────────────────────────
// On the hub canvas, small translucent "stage" panels orbit the central
// specimen pod, each tinted with its stage hue for wayfinding (the same hue
// carried by its connecting cable). A tint bundles the vivid line colour
// (dot / cable), a deep ink for text, and translucent glass fills.
interface LgStageTint {
  ink: string;
  line: string;
  bg: string;
  border: string;
}

function lgStageTint(line: string, ink: string): LgStageTint {
  return { line, ink, bg: `${line}14`, border: `${line}3d` };
}

export const lgStage = {
  source: lgStageTint("#f59e0b", "#b45309"),
  metadata: lgStageTint("#22c55e", "#15803d"),
  hbom: lgStageTint("#0f766e", "#115e59"),
  runtime: lgStageTint("#0891b2", "#155e75"),
  sbom: lgStageTint("#16a34a", "#15803d"),
  swh: lgStageTint("#e4572e", "#9a3412"),
  archive: lgStageTint("#059669", "#065f46"),
  activation: lgStageTint("#7c3aed", "#5b21b6"),
  evaluate: lgStageTint("#7c3aed", "#5b21b6"),
  experiments: lgStageTint("#4f46e5", "#3730a3"),
  danger: lgStageTint("#e11d48", "#be123c"),
} as const;

export function lgSegmentedTab(active: boolean): React.CSSProperties {
  return {
    ...S_ACTION_BUTTON_BASE,
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    minHeight: 38,
    borderRadius: 9,
    padding: "8px 13px",
    border: active ? "1px solid rgba(14, 165, 233, 0.58)" : lgBorders.actionNeutral,
    background: active ? "rgba(239, 246, 255, 0.94)" : "rgba(255, 255, 255, 0.58)",
    color: active ? lgColors.primaryDeep : lgColors.textMid,
    boxShadow: active ? "0 12px 26px rgba(14, 165, 233, 0.16)" : "none",
    cursor: "pointer",
    fontFamily: F.sans,
    fontSize: 12,
    fontWeight: 800,
  };
}
