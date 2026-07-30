import {
  emptyReproducibilityScoreCard,
  SCORECARD_CATEGORY_COLORS,
  type ScoreCardCategory,
  type ScoreCardRung,
} from "@core/scorecard/ReproducibilityScoreCard";
import { useReproducibilityScoreCard } from "@shell/data/scorecard/queries";
import { useState } from "react";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { HudConsole } from "./HudConsole";

interface ReproducibilityScoreCardConsoleProps {
  provisioned: boolean;
}

function rungLabel(rung: ScoreCardRung): string {
  if (rung.done != null && rung.total != null) {
    return `${rung.label} ${rung.done}/${rung.total}`;
  }
  return rung.label;
}

function RungPill({ rung, accent }: { rung: ScoreCardRung; accent: string }) {
  return (
    <span
      title={rung.detail || rung.label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 20,
        padding: "0 8px",
        borderRadius: 99,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: F.mono,
        whiteSpace: "nowrap",
        color: rung.reached ? accent : C.textMuted,
        background: rung.reached ? `${accent}14` : C.surfaceAlt,
        border: `1px solid ${rung.reached ? `${accent}55` : C.border}`,
      }}
    >
      {rungLabel(rung)}
    </span>
  );
}

function CategoryRow({ category }: { category: ScoreCardCategory }) {
  const accent = SCORECARD_CATEGORY_COLORS[category.key];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span
        style={{
          width: 84,
          flexShrink: 0,
          fontSize: 10.5,
          fontWeight: 800,
          letterSpacing: 0.4,
          textTransform: "uppercase",
          fontFamily: F.mono,
          color: C.textMid,
        }}
      >
        {category.label}
      </span>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {category.rungs.map((rung) => (
          <RungPill key={rung.key} rung={rung} accent={accent} />
        ))}
      </div>
    </div>
  );
}

// The REE evidence scorecard HUD — the top-centre console on the canvas. A
// plain report: five evidence categories with their rung states, plus the
// ordinal level (R0..R5) the backend derives from the persisted record
// (intent + session + run receipts). The level describes evidence maturity;
// it is not a claim that an independent reproduction has happened.
export function ReproducibilityScoreCardConsole({
  provisioned,
}: ReproducibilityScoreCardConsoleProps) {
  const [open, setOpen] = useState(false);

  const query = useReproducibilityScoreCard({ enabled: provisioned });
  // The lowest level is the honest default: an unmeasured REE *is* R0 Draft,
  // so absence of a server card never reads as a separate "unavailable" state.
  const card = query.data ?? emptyReproducibilityScoreCard();

  const levelTint = card.level >= 5 ? C.done : C.text;
  const subtitle = provisioned ? `${card.levelCode} · ${card.levelName}` : "awaiting workbench";

  return (
    <HudConsole
      open={open}
      onToggle={() => setOpen((value) => !value)}
      widthOpen={430}
      widthCollapsed={280}
      outerStyle={{ top: 16, left: "50%", transform: "translateX(-50%)" }}
      icon={Ic.star(14)}
      iconColor={provisioned ? SCORECARD_CATEGORY_COLORS.activation : C.textMuted}
      title="REE evidence"
      subtitle={<span style={{ color: levelTint }}>{subtitle}</span>}
      on={provisioned && !!query.data}
      expandLabel="Expand REE evidence scorecard"
      collapseLabel="Collapse REE evidence scorecard"
      bodyMaxHeight={520}
    >
      {card.categories.map((category) => (
        <CategoryRow key={category.key} category={category} />
      ))}
      <div
        style={{
          marginTop: 2,
          paddingTop: 7,
          borderTop: `1px dashed ${C.border}`,
          fontSize: 10,
          fontFamily: F.mono,
          color: C.textMuted,
        }}
      >
        {query.isError
          ? "Live scorecard unreachable — showing the R0 defaults."
          : card.sealed
            ? `Sealed at ${card.levelCode} · ${card.levelName} — an evidence level, not a reproduction verdict.`
            : "Derived from recorded evidence; seal to stamp the level. Not a reproduction verdict."}
      </div>
    </HudConsole>
  );
}
