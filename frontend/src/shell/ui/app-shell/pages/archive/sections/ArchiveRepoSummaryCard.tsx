import type { ArchiveRepo } from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import { C, F } from "../../../../theme/theme";

interface ArchiveRepoSummaryCardProps {
  repo: ArchiveRepo;
  assignedId?: string;
}

export function ArchiveRepoSummaryCard({ repo, assignedId }: ArchiveRepoSummaryCardProps) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1.5px solid ${repo.border}`,
        borderRadius: 10,
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          padding: "10px 16px",
          background: repo.bg,
          borderBottom: `1px solid ${repo.border}`,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div
          style={{
            width: 3,
            height: 16,
            borderRadius: 99,
            background: repo.color,
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 14, fontWeight: 700, color: repo.color, fontFamily: F.sans }}>
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
            opacity: 0.7,
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: 3,
          }}
        >
          {Ic.link(10)} {repo.url.replace("https://", "")}
        </a>
      </div>
      <div style={{ padding: "12px 16px" }}>
        <p style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, margin: "0 0 12px" }}>
          {repo.desc}
        </p>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "7px 10px",
            borderRadius: 7,
            background: assignedId ? repo.bg : C.surfaceAlt,
            border: `1px solid ${assignedId ? repo.border : C.border}`,
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 700,
              fontFamily: F.mono,
              color: assignedId ? repo.color : C.textMuted,
              flexShrink: 0,
            }}
          >
            {repo.idLabel}
          </span>
          <span
            style={{
              fontSize: 13,
              fontFamily: F.mono,
              color: assignedId ? repo.color : C.textMuted,
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
                fontSize: 11,
                color: repo.color,
                background: repo.bg,
                border: `1px solid ${repo.border}`,
                borderRadius: 3,
                padding: "1px 5px",
                fontFamily: F.mono,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              ✓ assigned
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
