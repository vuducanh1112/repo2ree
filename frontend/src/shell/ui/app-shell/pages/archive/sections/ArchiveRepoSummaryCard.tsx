import type { ArchiveRepo } from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import { lgColors, lgContentCard } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

interface ArchiveRepoSummaryCardProps {
  repo: ArchiveRepo;
  assignedId?: string;
}

export function ArchiveRepoSummaryCard({ repo, assignedId }: ArchiveRepoSummaryCardProps) {
  return (
    <div style={{ ...lgContentCard(0), borderColor: `${repo.color}40` }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            width: 3,
            height: 16,
            borderRadius: 99,
            background: repo.color,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 14, fontWeight: 800, color: repo.color, fontFamily: F.sans }}>
          {repo.label}
        </span>
        <a
          href={repo.url}
          target="_blank"
          rel="noreferrer"
          style={{
            marginLeft: "auto",
            fontSize: 11,
            fontFamily: F.mono,
            color: repo.color,
            opacity: 0.85,
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          {Ic.link(11)} {repo.url.replace("https://", "")}
        </a>
      </div>

      <p style={{ fontSize: 13, color: lgColors.textMid, lineHeight: 1.6, margin: "0 0 12px" }}>
        {repo.desc}
      </p>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "9px 12px",
          borderRadius: 8,
          background: assignedId ? `${repo.color}12` : "rgba(255, 255, 255, 0.55)",
          border: `1px solid ${assignedId ? `${repo.color}55` : "rgba(148, 163, 184, 0.3)"}`,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 800,
            fontFamily: F.mono,
            letterSpacing: 0.4,
            textTransform: "uppercase",
            color: assignedId ? repo.color : lgColors.textMuted,
            flexShrink: 0,
          }}
        >
          {repo.idLabel}
        </span>
        <span
          style={{
            fontSize: 13,
            fontFamily: F.mono,
            color: assignedId ? repo.color : lgColors.textMuted,
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {assignedId || repo.idPlaceholder}
        </span>
        {assignedId && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              fontWeight: 700,
              fontFamily: F.sans,
              color: repo.color,
              background: "rgba(255, 255, 255, 0.7)",
              border: `1px solid ${repo.color}55`,
              borderRadius: 99,
              padding: "2px 8px",
              flexShrink: 0,
            }}
          >
            {Ic.check(10)} assigned
          </span>
        )}
      </div>
    </div>
  );
}
