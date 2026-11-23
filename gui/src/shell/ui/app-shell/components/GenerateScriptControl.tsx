import type { ScriptInferenceOutcome } from "@shell/data/scriptInference/mutations";
import { renderDecisionDiagram, renderDecisionTrace } from "@shell/data/scriptInference/traceAscii";
import { Button } from "@shell/ui/shared/components/Button";
import { Ic } from "@shell/ui/shared/components/Icon";
import type { UseMutationResult } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import styles from "./GenerateScriptControl.module.css";

type Tone = "ok" | "info" | "warn" | "error";
interface Status {
  tone: Tone;
  message: string;
}

interface Props {
  generate: UseMutationResult<ScriptInferenceOutcome, Error, void>;
  onLoad: (body: string) => void;
  noun: string;
  notInferredHint?: string;
  onExperimentEnvironmentPath?: (path: string) => void;
  disabled?: boolean;
  label?: string;
}

export function GenerateScriptControl({
  generate,
  onLoad,
  noun,
  notInferredHint,
  onExperimentEnvironmentPath,
  disabled = false,
  label = "Generate from repository",
}: Props) {
  const [status, setStatus] = useState<Status | null>(null);
  const [traceText, setTraceText] = useState<string | null>(null);

  const handleGenerate = useCallback(() => {
    setStatus(null);
    generate.mutate(undefined, {
      onSuccess: ({ generation, trace, dag }) => {
        setTraceText(
          dag && trace
            ? renderDecisionDiagram(dag, trace)
            : trace
              ? renderDecisionTrace(trace)
              : null,
        );
        if (generation.status === "not_inferred") {
          const hint = notInferredHint ? ` ${notInferredHint}` : "";
          const why =
            generation.blockingMessages.length > 0
              ? ` ${generation.blockingMessages.join(" ")}`
              : "";
          setStatus({
            tone: "warn",
            message: `No ${noun} could be inferred yet.${hint}${why} See the decision graph below.`,
          });
          return;
        }
        onLoad(generation.script.body);
        if (generation.script.experimentEnvironmentPath)
          onExperimentEnvironmentPath?.(generation.script.experimentEnvironmentPath);
        const parts = [`Loaded a generated ${noun} (${generation.script.ruleId}).`];
        if (generation.script.alternativeCount > 1) {
          parts.push(
            `${generation.script.alternativeCount} alternatives were available — review before saving.`,
          );
        }
        for (const message of generation.script.blockingMessages) parts.push(message);
        parts.push("Review it, then save to keep it.");
        const tone: Tone =
          generation.script.application === "confirmation_required" ? "info" : "ok";
        setStatus({ tone, message: parts.join(" ") });
      },
      onError: (error) => {
        setTraceText(null);
        setStatus({
          tone: "error",
          message: `Generation failed: ${error instanceof Error ? error.message : String(error)}`,
        });
      },
    });
  }, [generate, onLoad, noun, notInferredHint, onExperimentEnvironmentPath]);

  return (
    <div className={styles.control}>
      <div className={styles.row}>
        <Button
          variant="secondary"
          size="small"
          onClick={handleGenerate}
          disabled={disabled || generate.isPending}
          busy={generate.isPending}
          icon={generate.isPending ? Ic.loader(14) : Ic.fileCode(14)}
          title={`Infer a ${noun} from the built experiment environment. It loads into the editor below; nothing is saved until you save.`}
        >
          {generate.isPending ? "Generating…" : label}
        </Button>
        {status && (
          <span className={styles.status} data-tone={status.tone}>
            {status.message}
          </span>
        )}
      </div>
      {traceText && (
        <details>
          <summary className={styles.summary}>Decision graph</summary>
          <pre className={styles.trace}>{traceText}</pre>
        </details>
      )}
    </div>
  );
}
