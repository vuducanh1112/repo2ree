import { hbomSummaryLines } from "../../../core/hbom/HbomSummary";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import { Ic } from "../../shared/components/Icon";
import { LevelBadge } from "../../shared/components/LevelBadge";
import { C, F, hoverBg, S_SECTION_LABEL_SMALL } from "../../theme/theme";
import { MetaRow, RvProvenanceChain } from "../reviewerSupport";

interface ReviewerSidebarProps {
  ree: ReeEditorViewModel;
  level: number;
  levelMeta: {
    bg: string;
    color: string;
  };
  sealDate: string;
  reviewerPage: "review" | "files";
  fileCount: number;
  setReviewerPage: (page: "review" | "files") => void;
}

function ReviewerNavButton({
  active,
  icon,
  label,
  onClick,
  levelMeta,
}: {
  active: boolean;
  icon: JSX.Element;
  label: string;
  onClick: () => void;
  levelMeta: { bg: string; color: string };
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        border: `1px solid ${active ? levelMeta.color : C.border}`,
        borderRadius: 7,
        background: active ? levelMeta.bg : C.surface,
        color: active ? levelMeta.color : C.textMid,
        fontSize: 12,
        fontWeight: 600,
        fontFamily: F.sans,
        padding: "7px 9px",
        cursor: "pointer",
        textAlign: "left",
      }}
      {...hoverBg(C.surfaceAlt, active ? levelMeta.bg : C.surface)}
    >
      <span style={{ display: "flex" }}>{icon}</span>
      {label}
    </button>
  );
}

export function ReviewerSidebar({
  ree,
  level,
  levelMeta,
  sealDate,
  reviewerPage,
  fileCount,
  setReviewerPage,
}: ReviewerSidebarProps) {
  const hardwareLines = hbomSummaryLines(ree.hardware_description);

  return (
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
        <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 10 }}>Navigation</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <ReviewerNavButton
            active={reviewerPage === "review"}
            icon={Ic.shield(13)}
            label="Review"
            onClick={() => setReviewerPage("review")}
            levelMeta={levelMeta}
          />
          <ReviewerNavButton
            active={reviewerPage === "files"}
            icon={Ic.file(13)}
            label={`Files (${fileCount})`}
            onClick={() => setReviewerPage("files")}
            levelMeta={levelMeta}
          />
        </div>
      </div>

      <div style={{ padding: "14px 16px", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 10 }}>Metadata</div>
        <MetaRow label="Origin URL" value={ree.origin_url} mono href={ree.origin_url} />
        <MetaRow label="Runtime" value={ree.runtime} mono color={C.textMid} />
        <MetaRow label="Build Script" value={ree.build_runtime_script} mono color={C.textMid} />
        <MetaRow label="Activation Script" value={ree.activation_script} mono color={C.textMid} />
        <MetaRow label="SBOM" value={ree.sbom} mono color={C.textMid} />
        {hardwareLines.length > 0 && (
          <div style={{ paddingTop: 8 }}>
            <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 6 }}>Hardware BOM</div>
            {hardwareLines.map((line) => (
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
        <div style={{ ...S_SECTION_LABEL_SMALL, marginBottom: 12 }}>Provenance</div>
        <RvProvenanceChain ree={ree} />
      </div>
    </aside>
  );
}
