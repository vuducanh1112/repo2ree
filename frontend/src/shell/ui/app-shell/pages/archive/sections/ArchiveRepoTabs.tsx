import type { Badges } from "../../../../../../core/ree/ReeTypes";
import type { ArchiveRepo } from "../../../../../../core/ree-assembly/assemblyStepTypes";
import { Ic } from "../../../../shared/components/Icon";
import { C, F, hoverBg, hoverBorderColor, hoverIf } from "../../../../theme/theme";

interface ArchiveRepoTabsProps {
  repositories: ArchiveRepo[];
  activeRepo: string;
  badges: Badges;
  onSelect: (key: string) => void;
}

export function ArchiveRepoTabs({
  repositories,
  activeRepo,
  badges,
  onSelect,
}: ArchiveRepoTabsProps) {
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
      {repositories.map((archiveRepo) => {
        const isActive = activeRepo === archiveRepo.key;
        const isDone = !!badges[archiveRepo.key];
        return (
          <button
            type="button"
            key={archiveRepo.key}
            onClick={() => onSelect(archiveRepo.key)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "9px 16px",
              borderRadius: 8,
              border: `1.5px solid ${isActive ? archiveRepo.color : isDone ? `${archiveRepo.color}40` : C.border}`,
              background: isActive ? `${archiveRepo.color}10` : isDone ? archiveRepo.bg : C.surface,
              cursor: "pointer",
              transition: "all 0.15s",
              flex: 1,
              justifyContent: "center",
            }}
            {...hoverIf(
              !isActive,
              hoverBorderColor(
                `${archiveRepo.color}70`,
                isDone ? `${archiveRepo.color}40` : C.border,
              ),
            )}
            {...hoverIf(!isActive, hoverBg(archiveRepo.bg, isDone ? archiveRepo.bg : C.surface))}
          >
            {isDone && (
              <span style={{ color: archiveRepo.color, display: "flex" }}>{Ic.check(13)}</span>
            )}
            <span
              style={{
                fontSize: 13,
                fontWeight: isActive ? 700 : 500,
                color: isActive ? archiveRepo.color : isDone ? archiveRepo.color : C.textMid,
                fontFamily: F.sans,
              }}
            >
              {archiveRepo.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
