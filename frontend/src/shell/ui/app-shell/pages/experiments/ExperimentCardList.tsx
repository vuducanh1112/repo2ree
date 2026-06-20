import type { ExperimentResourceEstimates, ReeExperiment } from "@core/ree/ReeSpec";
import { Ic } from "@shell/ui/shared/components/Icon";
import {
  lgActionButton,
  lgColors,
  lgContentCard,
  lgGlassButton,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";
import { useState } from "react";
import { expId } from "./experimentsPageHelpers";

function hasResourceEstimates(estimates: ExperimentResourceEstimates): boolean {
  return Object.values(estimates).some((value) => value.trim() !== "");
}

export function ExperimentCardList({
  experiments,
  locked,
  onSelect,
  onAdd,
  onRemove,
}: {
  experiments: ReeExperiment[];
  locked: boolean;
  onSelect: (index: number) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  if (experiments.length === 0) {
    return <ExperimentEmptyState locked={locked} onAdd={onAdd} />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {experiments.map((exp, index) => (
        <ExperimentCard
          key={`exp-${String(index)}`}
          experiment={exp}
          index={index}
          locked={locked}
          onSelect={() => onSelect(index)}
          onRemove={() => onRemove(index)}
        />
      ))}
    </div>
  );
}

function ExperimentCard({
  experiment,
  index,
  locked,
  onSelect,
  onRemove,
}: {
  experiment: ReeExperiment;
  index: number;
  locked: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const name = experiment.name.trim();
  const command = experiment.command.trim();
  const description = experiment.description.trim();
  const outputCount = experiment.outputs?.length ?? 0;
  const runtimeEstimate = experiment.runtime_estimate.trim();
  const hasResources = hasResourceEstimates(experiment.resource_estimates);

  return (
    <div
      style={{
        border: hovered
          ? "1px solid rgba(14, 165, 233, 0.55)"
          : "1px solid rgba(125, 211, 252, 0.42)",
        borderRadius: 11,
        background: "rgba(255, 255, 255, 0.7)",
        boxShadow: hovered
          ? "0 14px 30px rgba(14, 165, 233, 0.16)"
          : "0 6px 16px rgba(15, 23, 42, 0.05)",
        transition: "border-color 0.15s, box-shadow 0.15s",
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={onSelect}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
        style={{
          width: "100%",
          textAlign: "left",
          background: "transparent",
          border: "none",
          padding: "14px 16px 12px",
          cursor: "pointer",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontFamily: F.mono,
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: "0.08em",
              color: lgColors.cyan,
              border: "1px solid rgba(14, 165, 233, 0.32)",
              background: "rgba(240, 249, 255, 0.85)",
              borderRadius: 6,
              padding: "2px 7px",
            }}
          >
            {expId(index)}
          </span>
          <h3
            style={{
              margin: 0,
              fontSize: 15,
              fontWeight: 700,
              color: name ? lgColors.text : lgColors.textMuted,
              fontStyle: name ? "normal" : "italic",
              flex: 1,
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {name || "untitled experiment"}
          </h3>
          {outputCount > 0 && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: lgColors.success,
                background: "rgba(220, 252, 231, 0.85)",
                border: "1px solid rgba(34, 197, 94, 0.35)",
                borderRadius: 99,
                padding: "2px 7px",
              }}
            >
              {outputCount} {outputCount === 1 ? "output" : "outputs"}
            </span>
          )}
          {runtimeEstimate && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: lgColors.blue,
                background: "rgba(238, 242, 255, 0.88)",
                border: "1px solid rgba(79, 70, 229, 0.28)",
                borderRadius: 99,
                padding: "2px 7px",
              }}
            >
              ~ {runtimeEstimate}
            </span>
          )}
          {hasResources && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: lgColors.cyan,
                background: "rgba(240, 249, 255, 0.88)",
                border: "1px solid rgba(14, 165, 233, 0.28)",
                borderRadius: 99,
                padding: "2px 7px",
              }}
            >
              resources
            </span>
          )}
          <span
            style={{
              color: hovered ? lgColors.blue : lgColors.textMuted,
              display: "flex",
              transition: "color 0.15s",
            }}
          >
            {Ic.chevR(15)}
          </span>
        </div>

        <div
          style={{
            fontFamily: F.mono,
            fontSize: 12,
            color: command ? lgColors.textMid : lgColors.textMuted,
            background: "rgba(248, 250, 252, 0.78)",
            border: "1px solid rgba(148, 163, 184, 0.28)",
            borderRadius: 7,
            padding: "7px 10px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            opacity: command ? 1 : 0.7,
          }}
        >
          {command || "no command set"}
        </div>

        {description && (
          <div
            style={{
              fontSize: 12,
              color: lgColors.textMid,
              lineHeight: 1.45,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {description}
          </div>
        )}
      </button>

      {!locked && (
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            padding: "0 12px 10px",
          }}
        >
          <button
            type="button"
            onClick={onRemove}
            style={{
              ...lgActionButton("danger"),
              width: "auto",
              padding: "4px 10px",
              fontSize: 11,
              fontWeight: 700,
              gap: 5,
            }}
          >
            {Ic.x(11)} Delete
          </button>
        </div>
      )}
    </div>
  );
}

function ExperimentEmptyState({ locked, onAdd }: { locked: boolean; onAdd: () => void }) {
  return (
    <div
      style={{
        ...lgContentCard(0),
        padding: "40px 24px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        textAlign: "center",
      }}
    >
      <span style={{ color: lgColors.cyan, display: "flex" }}>{Ic.terminal(28)}</span>
      <div style={{ fontSize: 14, fontWeight: 700, color: lgColors.text }}>No experiments yet</div>
      <div
        style={{
          fontSize: 12,
          color: lgColors.textMid,
          maxWidth: 320,
          lineHeight: 1.5,
        }}
      >
        Add a verification command and the assembled REE will be checked against it.
      </div>
      {!locked && (
        <button
          type="button"
          onClick={onAdd}
          style={{
            ...lgGlassButton(),
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 4,
          }}
        >
          {Ic.plus(13)} Add experiment
        </button>
      )}
    </div>
  );
}
