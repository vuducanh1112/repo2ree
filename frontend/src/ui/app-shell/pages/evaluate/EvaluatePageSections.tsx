import { LEVELS } from "../../../../core/review/levels";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import { Ic } from "../../../shared/components/Icon";
import { LevelBadge } from "../../../shared/components/LevelBadge";
import { C, F, S_FIELD_HELP_TEXT_SMALL } from "../../../theme/theme";
import { DependencyPanel } from "../../components/assemblyRunPanels";
import { FieldRow, FieldSection } from "../../components/fieldTips";
import {
  assemblyStatusBadgeStyle,
  assemblyToneIconStyle,
  assemblyTonePanelStyle,
  assemblyToneTextStyle,
} from "../../components/statusUiStyles";
import { countContainerAndNixFiles, EXPECTED_DEP_FILES } from "./EvaluatePageHelpers";

export function EvaluateScoreSection(props: {
  hasScoreOutput: boolean;
  level: number;
  completionPct: number;
  focusedField: string | null;
  onFocusField: (value: string) => void;
  icon: JSX.Element;
}) {
  const currentLevel = LEVELS[props.level];
  const standing = `${props.level + 1} / ${LEVELS.length}`;

  return (
    <FieldSection
      title="Evaluate Output · Reproducibility Score"
      icon={props.icon}
      filledCount={props.hasScoreOutput ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="repro_level"
        onFocus={() => props.onFocusField("repro_level")}
        active={props.focusedField === "repro_level"}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 10,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 12,
                color: props.hasScoreOutput ? currentLevel.ink : C.textMuted,
                marginTop: 2,
                fontWeight: props.hasScoreOutput ? 600 : 500,
              }}
            >
              {props.hasScoreOutput
                ? `Computed from latest completed Evaluate run · Standing level ${standing}`
                : "No Evaluate output yet. Complete a run to generate the level."}
            </div>
          </div>
          <LevelBadge level={props.level} />
        </div>

        <div
          style={{
            height: 7,
            borderRadius: 99,
            background: C.surfaceAlt,
            border: `1px solid ${C.border}`,
            overflow: "hidden",
            marginBottom: 12,
          }}
        >
          <div
            style={{
              width: `${props.hasScoreOutput ? props.completionPct : 0}%`,
              height: "100%",
              background: currentLevel.color,
              transition: "width 0.24s ease",
            }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {LEVELS.map((levelConfig, idx) => {
            const reached = props.hasScoreOutput && idx <= props.level;
            const active = props.hasScoreOutput && idx === props.level;
            return (
              <div
                key={levelConfig.n}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  padding: "7px 8px",
                  borderRadius: 8,
                  border: `1px solid ${active ? `${levelConfig.color}55` : C.border}`,
                  background: active ? levelConfig.bg : "transparent",
                  opacity: props.hasScoreOutput ? 1 : 0.9,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    fontFamily: F.mono,
                    color: reached ? levelConfig.ink : C.textMuted,
                    background: reached ? levelConfig.bg : C.surfaceAlt,
                    border: `1px solid ${reached ? `${levelConfig.color}55` : C.border}`,
                    borderRadius: 99,
                    padding: "1px 7px",
                    flexShrink: 0,
                    marginTop: 1,
                  }}
                >
                  L{levelConfig.n}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: active ? 700 : 600,
                      color: reached ? C.text : C.textMid,
                    }}
                  >
                    {levelConfig.label}
                  </div>
                  <div style={S_FIELD_HELP_TEXT_SMALL}>{levelConfig.desc}</div>
                  <div style={{ marginTop: 5, display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={assemblyTonePanelStyle("warn")}>
                      <span style={assemblyToneIconStyle("warn")}>{Ic.info(11)}</span>
                      <span style={assemblyToneTextStyle("warn")}>
                        {levelConfig.problem || "No major bottleneck called out at this level."}
                      </span>
                    </div>
                    <div style={assemblyTonePanelStyle("good")}>
                      <span style={assemblyToneIconStyle("good")}>{Ic.check(11)}</span>
                      <span style={assemblyToneTextStyle("good")}>
                        {levelConfig.fix || "No additional fix suggested at this level."}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </FieldRow>
    </FieldSection>
  );
}

export function EvaluateDependenciesSection(props: {
  hasRun: boolean;
  depGroups: ReturnType<
    typeof import("../../../../application/ree-assembly/assemblyDependencyAnalysis").scanDependencies
  >;
  files: FileTreeNode[];
  focusedField: string | null;
  onFocusField: (value: string) => void;
}) {
  const { containerCount, nixCount } = countContainerAndNixFiles(props.files || []);
  return (
    <FieldSection
      title="Detected Dependencies"
      icon={Ic.package()}
      subtitle={!props.hasRun ? "run to scan" : undefined}
      filledCount={props.depGroups.length > 0 ? 1 : 0}
      totalCount={1}
    >
      <FieldRow
        fieldKey="detected_dependencies"
        onFocus={() => props.onFocusField("detected_dependencies")}
        active={props.focusedField === "detected_dependencies"}
      >
        {props.hasRun ? (
          <>
            {props.depGroups.length > 0 ? (
              <DependencyPanel depGroups={props.depGroups} />
            ) : (
              <div
                style={{
                  border: `1.5px dashed ${C.borderMid}`,
                  borderRadius: 10,
                  padding: "16px",
                  textAlign: "center",
                  color: C.textMuted,
                  marginBottom: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    marginBottom: 6,
                    opacity: 0.4,
                  }}
                >
                  {Ic.package(20)}
                </div>
                <div style={{ fontSize: 12, fontFamily: F.sans }}>No manifest files found</div>
                <div style={{ fontSize: 11, color: C.textMuted, fontFamily: F.sans, marginTop: 3 }}>
                  Add requirements.txt, pyproject.toml, environment.yml, or package.json.
                </div>
              </div>
            )}

            <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span
                style={{
                  ...assemblyStatusBadgeStyle("#0e7490"),
                  fontSize: 11,
                  padding: "3px 10px",
                }}
              >
                Container files: {containerCount}
              </span>
              <span
                style={{
                  ...assemblyStatusBadgeStyle("#6d28d9"),
                  fontSize: 11,
                  padding: "3px 10px",
                }}
              >
                Nix files: {nixCount}
              </span>
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {EXPECTED_DEP_FILES.map((item) => (
              <div
                key={item.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "7px 10px",
                  border: `1.5px dashed ${item.color}30`,
                  borderRadius: 8,
                  background: `${item.color}05`,
                  opacity: 0.7,
                }}
              >
                <span style={{ display: "flex", color: item.color, opacity: 0.6 }}>
                  {Ic.file(12)}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: F.mono,
                    color: item.color,
                    fontWeight: 600,
                    flex: 1,
                  }}
                >
                  {item.label}
                </span>
                <span style={{ fontSize: 10, color: C.textMuted, fontFamily: F.sans }}>
                  {item.hint}
                </span>
              </div>
            ))}
          </div>
        )}
      </FieldRow>
    </FieldSection>
  );
}
