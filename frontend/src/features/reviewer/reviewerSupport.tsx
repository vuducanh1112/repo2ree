import type React from "react";
import { useEffect, useState } from "react";
import { Ic } from "../../components/Icon";
import { C, F, hoverColor, S_ACTION_BUTTON_BASE, S_SECTION_LABEL } from "../../constants/theme";
import type { LogLine, Ree } from "../../types/ree";
import type { ServiceParam, ServiceParamValue, StepState } from "../../types/services";
import { WorkflowLogSection } from "../explorer/components/workflow/servicePanels";

const actionBtn = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...S_ACTION_BUTTON_BASE,
  ...extra,
});

interface ReactivationStep {
  key: ReactivationStepKey;
  label: string;
  icon: (s?: number) => JSX.Element;
  color: string;
  desc: string;
  params?: ServiceParam[];
  logLines: (ree: Ree, params?: ReactivationParams) => LogLine[];
}

export type ReactivationStepKey = "acquire_source" | "build_runtime" | "test_activation";
export type ReactivationParams = Record<string, ServiceParamValue>;

export const REACTIVATION_STEPS: ReactivationStep[] = [
  {
    key: "acquire_source",
    label: "Acquire Source",
    icon: Ic.archive,
    color: "#0891b2",
    desc: "Acquire source when it is not included in the uploaded review package.",
    logLines: (ree) =>
      ree._sourceIncluded
        ? [
            { type: "info", msg: "Source already included in uploaded archive." },
            { type: "ok", msg: "Source acquisition skipped ✓" },
          ]
        : [
            { type: "info", msg: "Acquiring source snapshot…" },
            { type: "info", msg: `  Origin: ${ree.origin_url || "(not set)"}` },
            { type: "info", msg: `  SWHID:  ${ree.swhid || "(not set)"}` },
            { type: "info", msg: `  DOI:    ${ree.zenodo_doi || "(not set)"}` },
            { type: "ok", msg: "Source snapshot acquired ✓" },
          ],
  },
  {
    key: "build_runtime",
    label: "Build Runtime",
    icon: Ic.cpu,
    color: "#7c3aed",
    desc: "Execute the build script from scratch with --no-cache to reconstruct the container image.",
    params: [
      {
        key: "no_cache",
        label: "No cache",
        type: "bool",
        default: true,
        hint: "Pass --no-cache to docker build",
      },
      {
        key: "platform",
        label: "Platform",
        type: "select",
        default: "linux/amd64",
        options: ["linux/amd64", "linux/arm64"],
        hint: "Target platform",
      },
    ],
    logLines: (ree, params) => [
      { type: "info", msg: `Platform: ${params?.platform || "linux/amd64"}` },
      { type: "info", msg: `No-cache: ${params?.no_cache !== false ? "yes" : "no"}` },
      { type: "info", msg: `Running: bash ${ree.build_runtime_script}` },
      { type: "info", msg: "DOCKER_BUILDKIT=1 docker build --no-cache -t ree:latest ." },
      { type: "info", msg: "[1/6] FROM python:3.11.7-slim-bookworm" },
      { type: "info", msg: "[2/6] WORKDIR /app" },
      { type: "info", msg: "[3/6] COPY . ." },
      { type: "info", msg: "[4/6] RUN pip install --no-cache-dir -r requirements.txt" },
      { type: "info", msg: "  numpy==1.26.4 … installed" },
      { type: "info", msg: "  pandas==2.2.1 … installed" },
      { type: "info", msg: "  scipy==1.12.0 … installed" },
      { type: "info", msg: '[5/6] CMD ["python", "src/main.py"]' },
      { type: "info", msg: "Saving image as runtime.tar.gz …" },
      { type: "ok", msg: "Build complete — runtime.tar.gz produced (1.2 GB)" },
    ],
  },
  {
    key: "test_activation",
    label: "Test Activation",
    icon: Ic.shield,
    color: "#16a34a",
    desc: "Load the rebuilt runtime and run the activation script to verify the environment starts cleanly.",
    logLines: (ree) => [
      { type: "info", msg: `Running: bash ${ree.activation_script}` },
      { type: "info", msg: "docker load < runtime.tar.gz" },
      { type: "info", msg: "Loaded image: ree:latest" },
      { type: "info", msg: `docker run --rm --entrypoint="" ree:latest echo ok` },
      { type: "ok", msg: "ok" },
      { type: "ok", msg: "Activation test passed — container starts cleanly ✓" },
    ],
  },
];

interface MetaRowProps {
  label: string;
  value?: string;
  mono?: boolean;
  href?: string;
  color?: string;
}

export function MetaRow({ label, value, mono = false, href, color }: MetaRowProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!value) return;
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    });
  };

  if (!value) {
    return (
      <div
        style={{
          display: "flex",
          gap: 10,
          padding: "7px 0",
          borderBottom: `1px solid ${C.border}`,
          alignItems: "center",
        }}
      >
        <span
          style={{
            width: 130,
            fontSize: 11,
            color: C.textMuted,
            fontFamily: F.sans,
            flexShrink: 0,
          }}
        >
          {label}
        </span>
        <span style={{ fontSize: 11, fontFamily: F.mono, color: C.textMuted, fontStyle: "italic" }}>
          not set
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        padding: "7px 0",
        borderBottom: `1px solid ${C.border}`,
        alignItems: "center",
      }}
    >
      <span
        style={{
          width: 130,
          fontSize: 11,
          color: C.textMuted,
          fontFamily: F.sans,
          flexShrink: 0,
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <span
        style={{
          flex: 1,
          fontSize: 11,
          fontFamily: mono ? F.mono : F.sans,
          color: color || (mono ? C.accent : C.text),
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            style={{
              color: C.accent,
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              textDecoration: "none",
            }}
          >
            {value} {Ic.externalLink(10)}
          </a>
        ) : (
          value
        )}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        title="Copy"
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          color: copied ? "#22c55e" : C.textMuted,
          display: "flex",
          padding: 2,
          flexShrink: 0,
          borderRadius: 3,
          transition: "color 0.15s",
        }}
        {...hoverColor(C.textMid, copied ? "#22c55e" : C.textMuted)}
      >
        {copied ? Ic.check(11) : Ic.copy(11)}
      </button>
    </div>
  );
}

interface RvStepCardProps {
  step: ReactivationStep;
  index: number;
  state: StepState;
  log: LogLine[] | null;
  params: ReactivationParams;
  onSetParam: (stepKey: ReactivationStepKey, paramKey: string, value: ServiceParamValue) => void;
  onRun: (key: ReactivationStepKey, params: ReactivationParams) => boolean | Promise<boolean>;
  onCancel?: (key: ReactivationStepKey) => void | Promise<void>;
  isLast: boolean;
  prevDone: boolean;
}

export function RvStepCard({
  step,
  index,
  state,
  log,
  params,
  onSetParam,
  onRun,
  onCancel,
  isLast,
  prevDone,
}: RvStepCardProps) {
  const done = state === "done";
  const running = state === "loading";
  const locked = !prevDone && !done;
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (running) setExpanded(true);
  }, [running]);

  const col = done ? "#22c55e" : locked ? C.textMuted : step.color;
  const borderCol = done ? "#22c55e40" : locked ? C.border : `${step.color}30`;
  const bgCol = done ? "#f0fdf4" : locked ? C.bg : `${step.color}08`;

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          flexShrink: 0,
          width: 28,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            flexShrink: 0,
            background: done ? "#22c55e" : locked ? C.surfaceAlt : `${step.color}18`,
            border: `2px solid ${done ? "#22c55e" : locked ? C.borderMid : step.color}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: done ? "#fff" : locked ? C.textMuted : step.color,
            transition: "all 0.3s",
            boxShadow: done
              ? "0 0 0 3px #22c55e20"
              : running
                ? `0 0 0 3px ${step.color}25`
                : "none",
          }}
        >
          {done ? (
            Ic.check(11)
          ) : (
            <span
              style={{ animation: running ? "spin 0.9s linear infinite" : "none", display: "flex" }}
            >
              {running ? Ic.loader(11) : step.icon(11)}
            </span>
          )}
        </div>
        {!isLast && (
          <div
            style={{
              flex: 1,
              width: 2,
              minHeight: 20,
              marginTop: 4,
              background: done ? "#22c55e" : C.border,
              transition: "background 0.4s",
              borderRadius: 1,
            }}
          />
        )}
      </div>
      <div
        style={{
          flex: 1,
          marginBottom: isLast ? 0 : 14,
          background: bgCol,
          border: `1.5px solid ${borderCol}`,
          borderRadius: 10,
          overflow: "hidden",
          transition: "all 0.25s",
          opacity: locked ? 0.55 : 1,
        }}
      >
        <button
          type="button"
          onClick={() => !locked && setExpanded((isExpanded) => !isExpanded)}
          disabled={locked}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 9,
            padding: "11px 14px",
            background: "transparent",
            border: "none",
            cursor: locked ? "default" : "pointer",
            textAlign: "left",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 1 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  fontFamily: F.mono,
                  letterSpacing: 0.6,
                  color: col,
                  background: `${col}15`,
                  border: `1px solid ${col}30`,
                  borderRadius: 3,
                  padding: "0 5px",
                }}
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: locked ? C.textMuted : C.text,
                  fontFamily: F.sans,
                }}
              >
                {step.label}
              </span>
              {done && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#16a34a",
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 4,
                    padding: "1px 6px",
                  }}
                >
                  ✓ passed
                </span>
              )}
              {running && (
                <span
                  style={{
                    fontSize: 11,
                    color: step.color,
                    background: `${step.color}12`,
                    border: `1px solid ${step.color}30`,
                    borderRadius: 4,
                    padding: "1px 6px",
                  }}
                >
                  running…
                </span>
              )}
            </div>
            <span
              style={{ fontSize: 12, color: locked ? C.textMuted : C.textMid, fontFamily: F.sans }}
            >
              {step.desc}
            </span>
          </div>
          {!locked && (
            <span style={{ color: C.textMuted, display: "flex", flexShrink: 0 }}>
              {expanded ? Ic.chevD(12) : Ic.chevR(12)}
            </span>
          )}
        </button>
        {expanded && !locked && (
          <div
            style={{
              padding: "0 14px 14px",
              borderTop: `1px solid ${borderCol}`,
              background: "rgba(255,255,255,0.6)",
            }}
          >
            {step.params && step.params.length > 0 && (
              <div style={{ paddingTop: 12, marginBottom: 12 }}>
                <div
                  style={{
                    ...S_SECTION_LABEL,
                    fontSize: 10,
                    marginBottom: 10,
                  }}
                >
                  Parameters
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {step.params.map((p) => (
                    <div key={p.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: C.text,
                            fontFamily: F.sans,
                          }}
                        >
                          {p.label}
                        </div>
                        <div style={{ fontSize: 12, color: C.textMuted }}>{p.hint}</div>
                      </div>
                      {p.type === "bool" ? (
                        <button
                          type="button"
                          onClick={() => onSetParam(step.key, p.key, !params[p.key])}
                          style={{
                            width: 40,
                            height: 22,
                            borderRadius: 11,
                            border: "none",
                            cursor: "pointer",
                            background: params[p.key] ? step.color : C.borderMid,
                            position: "relative",
                            flexShrink: 0,
                            transition: "background 0.2s",
                          }}
                        >
                          <div
                            style={{
                              position: "absolute",
                              top: 2,
                              left: params[p.key] ? 20 : 2,
                              width: 18,
                              height: 18,
                              borderRadius: "50%",
                              background: "#fff",
                              transition: "left 0.2s",
                              boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                            }}
                          />
                        </button>
                      ) : p.type === "select" ? (
                        <select
                          value={String(params[p.key] ?? "")}
                          onChange={(event) => onSetParam(step.key, p.key, event.target.value)}
                          style={{
                            border: `1.5px solid ${C.border}`,
                            borderRadius: 6,
                            padding: "5px 8px",
                            fontSize: 13,
                            fontFamily: F.mono,
                            color: C.text,
                            background: C.surface,
                            flexShrink: 0,
                          }}
                        >
                          {(p.options ?? []).map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button
              type="button"
              onClick={() => onRun(step.key, params)}
              disabled={running}
              style={{
                ...actionBtn({
                  padding: "9px 14px",
                  borderRadius: 8,
                  border: done ? "1.5px solid #bbf7d0" : "none",
                  background: running ? `${step.color}20` : done ? "#f0fdf4" : step.color,
                  color: running ? step.color : done ? "#16a34a" : "#fff",
                  fontWeight: 600,
                }),
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 7,
                width: "100%",
                cursor: running ? "wait" : "pointer",
                marginBottom: log ? 12 : 0,
                boxShadow: !done && !running ? `0 2px 10px ${step.color}35` : "none",
              }}
            >
              <span
                style={{
                  display: "flex",
                  animation: running ? "spin 0.9s linear infinite" : "none",
                }}
              >
                {running ? Ic.loader(13) : done ? Ic.refresh(13) : Ic.play(13)}
              </span>
              {running ? "Running…" : done ? "Re-run" : `Run ${step.label}`}
            </button>
            {running && onCancel && (
              <button
                type="button"
                onClick={() => onCancel(step.key)}
                style={{
                  ...actionBtn({
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: "#fff1f2",
                    border: "1.5px solid #fecdd3",
                    color: "#be123c",
                    fontWeight: 700,
                  }),
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 7,
                  width: "100%",
                  marginBottom: log ? 12 : 0,
                }}
              >
                {Ic.x(13)} Cancel
              </button>
            )}
            {log && (
              <WorkflowLogSection
                log={{ lines: log, ts: log[log.length - 1]?.ts || new Date().toISOString() }}
                running={running}
                title="Output"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface RvVerdictBannerProps {
  allDone: boolean;
}

export function RvVerdictBanner({ allDone }: RvVerdictBannerProps) {
  if (!allDone) return null;
  return (
    <div
      style={{
        background: "linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)",
        border: "1.5px solid #22c55e40",
        borderRadius: 12,
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        boxShadow: "0 0 0 4px #22c55e10, 0 4px 20px rgba(34,197,94,0.12)",
        animation: "fadeUp 0.3s ease",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#22c55e",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          boxShadow: "0 0 0 6px #22c55e20",
        }}
      >
        {Ic.check(18)}
      </div>
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "#15803d",
            fontFamily: F.sans,
            marginBottom: 2,
          }}
        >
          Reactivation Verified — Reproducible ✓
        </div>
        <div style={{ fontSize: 13, color: "#166534", fontFamily: F.sans }}>
          All four stages passed. The sealed REE is byte-for-byte reproducible on this machine.
        </div>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 3,
          alignItems: "flex-end",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 11, color: "#166534", fontFamily: F.mono, fontWeight: 600 }}>
          {new Date().toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        <span style={{ fontSize: 10, color: "#16a34a", fontFamily: F.sans }}>by reviewer</span>
      </div>
    </div>
  );
}

interface RvProvenanceChainProps {
  ree: Ree;
}

export function RvProvenanceChain({ ree }: RvProvenanceChainProps) {
  const nodes = [
    {
      label: "Source Code",
      value: ree.origin_url,
      icon: Ic.link,
      color: "#0891b2",
      href: ree.origin_url,
    },
    {
      label: "Software Heritage",
      value: ree.swhid,
      icon: Ic.archive,
      color: "#e4572e",
      href: ree.swhid ? `https://archive.softwareheritage.org/${ree.swhid}` : null,
    },
    {
      label: "Zenodo DOI",
      value: ree.zenodo_doi,
      icon: Ic.globe,
      color: "#1d6fa4",
      href: ree.zenodo_doi ? `https://doi.org/${ree.zenodo_doi}` : null,
    },
    { label: "SBOM", value: ree.sbom, icon: Ic.package, color: "#16a34a" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {nodes.map((node, i) => {
        const set = !!node.value;
        const nodeValue = node.value ?? "";
        return (
          <div key={node.label} style={{ display: "flex", gap: 10, alignItems: "stretch" }}>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: 24,
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  background: set ? `${node.color}18` : C.surfaceAlt,
                  border: `2px solid ${set ? node.color : C.borderMid}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: set ? node.color : C.textMuted,
                  flexShrink: 0,
                }}
              >
                {node.icon(9)}
              </div>
              {i < nodes.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    width: 2,
                    background: set ? `${node.color}40` : C.border,
                    minHeight: 10,
                  }}
                />
              )}
            </div>
            <div
              style={{
                flex: 1,
                paddingBottom: i < nodes.length - 1 ? 10 : 0,
                paddingTop: 1,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: set ? C.textMid : C.textMuted,
                  fontFamily: F.sans,
                  marginBottom: 1,
                }}
              >
                {node.label}
              </div>
              {set ? (
                node.href ? (
                  <a
                    href={node.href}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: node.color,
                      textDecoration: "none",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                      maxWidth: "100%",
                    }}
                  >
                    {nodeValue.length > 50 ? `${nodeValue.slice(0, 50)}…` : nodeValue}
                  </a>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontFamily: F.mono,
                      color: node.color,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "block",
                    }}
                  >
                    {nodeValue}
                  </span>
                )
              ) : (
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: F.sans,
                    color: C.textMuted,
                    fontStyle: "italic",
                  }}
                >
                  not set
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
