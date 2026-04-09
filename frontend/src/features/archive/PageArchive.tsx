import { useState } from "react";
import { Ic } from "../../components/Icon";
import { ARCHIVE_REPOS } from "../../constants/archiveRepos";
import { type ExplorerPage, PAGE } from "../../constants/pages";
import {
  C,
  F,
  hoverBg,
  hoverBorderColor,
  hoverIf,
  S_FIELD_STACK_GAP_14,
  S_FLEX_ROW_GAP_8,
  S_SECTION_LABEL,
} from "../../constants/theme";
import type { ActionStates, Badges, Ree, ServiceLogs } from "../../types/ree";
import type { GenericServiceParams } from "../../types/services";
import { LogPanel } from "../explorer/components/inputs/logPanel";
import {
  NextStepNudge,
  RequirementsBanner,
  WorkflowPageHeader,
} from "../explorer/components/workflow/pageChrome";

export interface PageArchiveProps {
  ree: Ree;
  badges: Badges;
  logs: ServiceLogs;
  actionStates: ActionStates;
  onRun: (key: string, params: GenericServiceParams) => void;
  onGo: (key: ExplorerPage) => void;
}

export function PageArchive({ ree, badges, logs, actionStates, onRun, onGo }: PageArchiveProps) {
  const [activeRepo, setActiveRepo] = useState("swh");
  const repo =
    ARCHIVE_REPOS.find((archiveRepo) => archiveRepo.key === activeRepo) || ARCHIVE_REPOS[0];
  const earned = !!badges[activeRepo];
  const running = actionStates[activeRepo] === "loading";
  const log = logs[activeRepo];
  const [params, setParams] = useState<Record<string, string | boolean>>(() =>
    Object.fromEntries(
      ARCHIVE_REPOS.flatMap((archiveRepo) =>
        archiveRepo.params.map((param) => [`${archiveRepo.key}_${param.key}`, param.default]),
      ),
    ),
  );

  const getParam = (repoKey: string, paramKey: string): string | boolean =>
    params[`${repoKey}_${paramKey}`];

  const setParam = (repoKey: string, paramKey: string, val: string | boolean) =>
    setParams((prevParams) => ({ ...prevParams, [`${repoKey}_${paramKey}`]: val }));

  const missing = repo.requires.filter((requiredField) => !ree[requiredField.field]);
  const canRun = missing.length === 0 && !running;

  const assignedId = ree[repo.idField] as string | undefined;

  const buildDone = !!badges.build;
  const sbomDone = !!badges.sbom;
  const activationDone = !!badges.activation;
  const capstoneReady = buildDone && sbomDone && activationDone;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
        overflow: "hidden",
        animation: "fadeUp 0.2s ease",
      }}
    >
      <WorkflowPageHeader
        color={repo.color}
        icon={Ic.globe(18)}
        title="Deposit & Share"
        subtitle="Deposit your REE to a long-term archive and receive a citable permanent identifier"
        tips={[
          "Complete Build Runtime, SBOM, and Activation before depositing.",
          "Choose one repository and provide the parameters required by that archive.",
        ]}
      />

      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        <div style={{ padding: 24, maxWidth: 860 }}>
          {!capstoneReady && (
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 12,
                padding: "12px 16px",
                marginBottom: 20,
                background: "#fffbeb",
                border: "1px solid #fde68a",
                borderRadius: 10,
              }}
            >
              <span style={{ color: "#b45309", display: "flex", flexShrink: 0, marginTop: 1 }}>
                {Ic.info()}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#92400e", marginBottom: 4 }}>
                  Complete earlier steps before depositing
                </div>
                <div style={{ fontSize: 13, color: "#92400e", lineHeight: 1.5, marginBottom: 8 }}>
                  Archiving before building and validating risks depositing an environment that
                  can't be reproduced. Complete these steps first:
                </div>
                <div style={S_FLEX_ROW_GAP_8}>
                  {!buildDone && (
                    <span
                      style={{
                        fontSize: 12,
                        fontFamily: F.sans,
                        color: "#92400e",
                        background: "#fef3c7",
                        border: "1px solid #fde68a",
                        borderRadius: 4,
                        padding: "2px 8px",
                        fontWeight: 600,
                      }}
                    >
                      ✗ Build Runtime not run
                    </span>
                  )}
                  {!sbomDone && (
                    <span
                      style={{
                        fontSize: 12,
                        fontFamily: F.sans,
                        color: "#92400e",
                        background: "#fef3c7",
                        border: "1px solid #fde68a",
                        borderRadius: 4,
                        padding: "2px 8px",
                        fontWeight: 600,
                      }}
                    >
                      ✗ SBOM not generated
                    </span>
                  )}
                  {!activationDone && (
                    <span
                      style={{
                        fontSize: 12,
                        fontFamily: F.sans,
                        color: "#92400e",
                        background: "#fef3c7",
                        border: "1px solid #fde68a",
                        borderRadius: 4,
                        padding: "2px 8px",
                        fontWeight: 600,
                      }}
                    >
                      ✗ Activation test not run
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            {ARCHIVE_REPOS.map((archiveRepo) => {
              const isActive = activeRepo === archiveRepo.key;
              const isDone = !!badges[archiveRepo.key];
              return (
                <button
                  type="button"
                  key={archiveRepo.key}
                  onClick={() => setActiveRepo(archiveRepo.key)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "9px 16px",
                    borderRadius: 8,
                    border: `1.5px solid ${isActive ? archiveRepo.color : isDone ? `${archiveRepo.color}40` : C.border}`,
                    background: isActive
                      ? `${archiveRepo.color}10`
                      : isDone
                        ? archiveRepo.bg
                        : C.surface,
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
                  {...hoverIf(
                    !isActive,
                    hoverBg(archiveRepo.bg, isDone ? archiveRepo.bg : C.surface),
                  )}
                >
                  {isDone && (
                    <span style={{ color: archiveRepo.color, display: "flex" }}>
                      {Ic.check(13)}
                    </span>
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

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={S_FIELD_STACK_GAP_14}>
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
                  <span
                    style={{ fontSize: 14, fontWeight: 700, color: repo.color, fontFamily: F.sans }}
                  >
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
                  <p
                    style={{ fontSize: 13, color: C.textMid, lineHeight: 1.6, margin: "0 0 12px" }}
                  >
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

              <div
                style={{
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 10,
                  overflow: "hidden",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                }}
              >
                <div
                  style={{
                    padding: "8px 16px",
                    background: "#fafbfd",
                    borderBottom: `1px solid ${C.border}`,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 3,
                      height: 14,
                      borderRadius: 99,
                      background: C.borderMid,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ ...S_SECTION_LABEL, letterSpacing: 1 }}>Parameters</span>
                </div>
                <div
                  style={{
                    padding: "10px 16px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  {repo.params.map((p) => (
                    <div key={p.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                        <label
                          htmlFor={`repo-${repo.key}-param-${p.key}`}
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: C.textMid,
                            fontFamily: F.sans,
                          }}
                        >
                          {p.label}
                        </label>
                        <span style={{ fontSize: 12, color: C.textMuted }}>{p.hint}</span>
                      </div>
                      {p.type === "bool" ? (
                        <button
                          id={`repo-${repo.key}-param-${p.key}`}
                          type="button"
                          onClick={() => setParam(repo.key, p.key, !getParam(repo.key, p.key))}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 7,
                            padding: "6px 10px",
                            borderRadius: 6,
                            border: `1.5px solid ${getParam(repo.key, p.key) ? C.accent : C.border}`,
                            background: getParam(repo.key, p.key) ? C.accentBg : C.bg,
                            cursor: "pointer",
                            width: "fit-content",
                            transition: "all 0.15s",
                          }}
                        >
                          <div
                            style={{
                              width: 30,
                              height: 16,
                              borderRadius: 99,
                              background: getParam(repo.key, p.key) ? C.accent : C.borderMid,
                              position: "relative",
                              transition: "background 0.2s",
                            }}
                          >
                            <div
                              style={{
                                position: "absolute",
                                top: 2,
                                left: getParam(repo.key, p.key) ? 16 : 2,
                                width: 12,
                                height: 12,
                                borderRadius: "50%",
                                background: "#fff",
                                transition: "left 0.2s",
                              }}
                            />
                          </div>
                          <span
                            style={{
                              fontSize: 13,
                              fontFamily: F.sans,
                              color: getParam(repo.key, p.key) ? C.accent : C.textMuted,
                            }}
                          >
                            {getParam(repo.key, p.key) ? "yes" : "no"}
                          </span>
                        </button>
                      ) : p.type === "select" ? (
                        <select
                          id={`repo-${repo.key}-param-${p.key}`}
                          value={String(getParam(repo.key, p.key) ?? "")}
                          onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                          style={{
                            border: `1.5px solid ${C.border}`,
                            borderRadius: 7,
                            padding: "6px 10px",
                            fontSize: 14,
                            fontFamily: F.mono,
                            color: C.text,
                            background: C.surface,
                          }}
                        >
                          {(p.options ?? []).map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id={`repo-${repo.key}-param-${p.key}`}
                          value={String(getParam(repo.key, p.key) ?? "")}
                          onChange={(event) => setParam(repo.key, p.key, event.target.value)}
                          style={{
                            border: `1.5px solid ${C.border}`,
                            borderRadius: 7,
                            padding: "6px 10px",
                            fontSize: 14,
                            fontFamily: F.mono,
                            color: C.text,
                            background: C.surface,
                          }}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {missing.length > 0 && <RequirementsBanner status="missing" items={missing} />}

              <button
                type="button"
                onClick={() =>
                  canRun &&
                  onRun(
                    repo.key,
                    Object.fromEntries(repo.params.map((p) => [p.key, getParam(repo.key, p.key)])),
                  )
                }
                disabled={!canRun}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                  padding: "11px",
                  borderRadius: 9,
                  background: !canRun ? C.surfaceAlt : earned ? repo.bg : repo.color,
                  border: earned ? `1.5px solid ${repo.border}` : "none",
                  color: !canRun ? C.textMuted : earned ? repo.color : "#fff",
                  fontSize: 15,
                  fontWeight: 700,
                  fontFamily: F.sans,
                  cursor: canRun ? "pointer" : "default",
                  boxShadow: canRun && !earned ? `0 2px 12px ${repo.color}40` : "none",
                  transition: "all 0.2s",
                }}
              >
                <span
                  style={{
                    display: "flex",
                    animation: running ? "spin 0.9s linear infinite" : "none",
                  }}
                >
                  {running ? Ic.loader(15) : earned ? Ic.check(15) : Ic.upload(15)}
                </span>
                {running
                  ? `Depositing to ${repo.label}…`
                  : earned
                    ? `Re-deposit to ${repo.label}`
                    : `Deposit to ${repo.label}`}
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ ...S_SECTION_LABEL, letterSpacing: 1.3, fontWeight: 600 }}>Output</div>
              <LogPanel log={log} running={running} />
            </div>
          </div>

          <div style={{ padding: "24px 24px 24px", flexShrink: 0 }}>
            <NextStepNudge stepKey={PAGE.ARCHIVE} badges={badges || {}} onGo={onGo} />
          </div>
        </div>
      </div>
    </div>
  );
}
