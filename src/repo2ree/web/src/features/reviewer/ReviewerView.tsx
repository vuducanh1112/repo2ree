import { useState } from "react";
import { Ic } from "../../components/Icon";
import { LevelBadge } from "../../components/LevelBadge";
import { LEVELS } from "../../constants/levels";
import { C, F, hoverBg, hoverColor, S_SECTION_LABEL_SMALL } from "../../constants/theme";
import type { LogLine, Ree } from "../../types/ree";
import type { Level, ServiceParamValue, StepState } from "../../types/services";
import {
  MetaRow,
  REACTIVATION_STEPS,
  type ReactivationParams,
  type ReactivationStepKey,
  RvProvenanceChain,
  RvStepCard,
  RvVerdictBanner,
} from "./reviewerSupport";

interface ReviewerViewProps {
  ree?: Ree;
  onBack: () => void;
  defaultRee: Ree;
  PodOrbitControl: React.ComponentType<{
    level: number;
    levelMeta: Level;
    stepStates: Record<string, StepState>;
    allDone: boolean;
    isRunningAll: boolean;
    onRunAll: () => void;
  }>;
}

export function ReviewerView({
  ree: reeInput,
  onBack,
  defaultRee,
  PodOrbitControl,
}: ReviewerViewProps) {
  const ree = reeInput || defaultRee;
  const level = ree._evalLevel ?? 5;
  const levelMeta = LEVELS[Math.min(level, 7)];
  const sealDate = ree._sealedAt
    ? new Date(ree._sealedAt).toLocaleString([], {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "unknown";

  const [stepStates, setStepStates] = useState<Partial<Record<ReactivationStepKey, StepState>>>({});
  const [stepLogs, setStepLogs] = useState<Partial<Record<ReactivationStepKey, LogLine[]>>>({});
  const initParams = (): Record<ReactivationStepKey, ReactivationParams> =>
    Object.fromEntries(
      REACTIVATION_STEPS.map((step) => [
        step.key,
        Object.fromEntries((step.params || []).map((param) => [param.key, param.default])),
      ]),
    ) as Record<ReactivationStepKey, ReactivationParams>;
  const [stepParams, setStepParams] =
    useState<Record<ReactivationStepKey, ReactivationParams>>(initParams);

  const setParam = (stepKey: ReactivationStepKey, paramKey: string, val: ServiceParamValue) =>
    setStepParams((p) => ({ ...p, [stepKey]: { ...p[stepKey], [paramKey]: val } }));

  const runStep = async (key: ReactivationStepKey, params: ReactivationParams) => {
    const step = REACTIVATION_STEPS.find((reactivationStep) => reactivationStep.key === key);
    if (!step) return;
    setStepStates((prevStates) => ({ ...prevStates, [key]: "loading" }));
    setStepLogs((prevLogs) => ({ ...prevLogs, [key]: step.logLines(ree, params) }));
    await new Promise((resolve) =>
      setTimeout(resolve, 1200 + step.logLines(ree, params).length * 80),
    );
    setStepStates((prevStates) => ({ ...prevStates, [key]: "done" }));
  };

  const allDone = REACTIVATION_STEPS.every(
    (reactivationStep) => stepStates[reactivationStep.key] === "done",
  );
  const isRunningAll = REACTIVATION_STEPS.some(
    (reactivationStep) => stepStates[reactivationStep.key] === "loading",
  );

  const runAll = async () => {
    for (const step of REACTIVATION_STEPS) {
      if (stepStates[step.key] === "done") continue;
      await runStep(step.key, stepParams[step.key]);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      <header
        style={{
          height: 48,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 16px",
          position: "sticky",
          top: 0,
          zIndex: 100,
          flexShrink: 0,
          boxShadow: "0 1px 0 rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 5,
            color: C.textMuted,
            padding: "4px 8px",
            borderRadius: 6,
            transition: "all 0.12s",
          }}
          {...hoverColor(C.textMid, C.textMuted)}
          {...hoverBg(C.surfaceAlt, "transparent")}
        >
          {Ic.arrowLeft()}
          <span style={{ fontSize: 13, fontFamily: F.sans }}>back</span>
        </button>
        <div style={{ width: 1, height: 18, background: C.border }} />
        <span style={{ color: C.accent, display: "flex" }}>{Ic.layers()}</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
          REE Explorer
        </span>
        <span style={{ fontSize: 13, color: C.borderMid, fontFamily: F.mono }}>/</span>
        <span style={{ fontSize: 13, color: C.textMuted, fontFamily: F.mono }}>
          {ree.name || "untitled"}
        </span>
        <div style={{ flex: 1 }} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            background: "#fef3c7",
            border: "1px solid #fde68a",
            borderRadius: 6,
          }}
        >
          <span style={{ color: "#b45309", display: "flex" }}>{Ic.star(12)}</span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "#92400e",
              fontFamily: F.sans,
              letterSpacing: 0.3,
            }}
          >
            REVIEWER MODE
          </span>
        </div>
      </header>

      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
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
            <div
              style={{
                ...S_SECTION_LABEL_SMALL,
                marginBottom: 10,
              }}
            >
              Metadata
            </div>
            <MetaRow label="Origin URL" value={ree.origin_url} mono href={ree.origin_url} />
            <MetaRow label="Runtime" value={ree.runtime} mono color={C.textMid} />
            <MetaRow label="Build Script" value={ree.build_runtime_script} mono color={C.textMid} />
            <MetaRow
              label="Activation Script"
              value={ree.activation_script}
              mono
              color={C.textMid}
            />
            <MetaRow label="SBOM" value={ree.sbom} mono color={C.textMid} />
            {ree.hardware_description && (
              <div style={{ paddingTop: 8 }}>
                <div
                  style={{
                    ...S_SECTION_LABEL_SMALL,
                    marginBottom: 6,
                  }}
                >
                  Hardware
                </div>
                {Object.entries(ree.hardware_description)
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <div
                      key={k}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 11,
                        marginBottom: 3,
                      }}
                    >
                      <span style={{ color: C.textMuted, fontFamily: F.sans }}>{k}</span>
                      <span style={{ fontFamily: F.mono, color: C.textMid }}>{v}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
          <div style={{ padding: "14px 16px" }}>
            <div
              style={{
                ...S_SECTION_LABEL_SMALL,
                marginBottom: 12,
              }}
            >
              Provenance
            </div>
            <RvProvenanceChain ree={ree} />
          </div>
        </aside>

        <main
          style={{
            flex: 1,
            overflowY: "auto",
            minWidth: 0,
            background: `linear-gradient(180deg, ${levelMeta.bg}50 0%, ${C.bg} 320px)`,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              borderBottom: `1px solid ${C.border}`,
              paddingBottom: 28,
            }}
          >
            <PodOrbitControl
              level={level}
              levelMeta={levelMeta}
              stepStates={stepStates}
              allDone={allDone}
              isRunningAll={isRunningAll}
              onRunAll={runAll}
            />
          </div>
          <div style={{ padding: "20px 28px" }}>
            {allDone && (
              <div style={{ marginBottom: 20 }}>
                <RvVerdictBanner allDone={allDone} />
              </div>
            )}
            <div style={{ maxWidth: 660 }}>
              {REACTIVATION_STEPS.map((step, i) => {
                const prevDone = i === 0 || stepStates[REACTIVATION_STEPS[i - 1].key] === "done";
                return (
                  <RvStepCard
                    key={step.key}
                    step={step}
                    index={i}
                    state={stepStates[step.key] || "idle"}
                    log={stepLogs[step.key] || null}
                    params={stepParams[step.key]}
                    onSetParam={setParam}
                    onRun={runStep}
                    isLast={i === REACTIVATION_STEPS.length - 1}
                    prevDone={prevDone}
                  />
                );
              })}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
