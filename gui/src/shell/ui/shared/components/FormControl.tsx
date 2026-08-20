import {
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useId,
} from "react";
import styles from "./FormControl.module.css";

/** The composable field primitives.
 *
 * `Field` exists for the association a hand-rolled label/helper pair keeps
 * getting wrong: the control gets a generated id, the label points at it, and
 * the hint is wired through `aria-describedby` so it is read out rather than
 * merely displayed.
 */

interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  error?: ReactNode;
  /** Receives the ids to bind. A render prop because the control is arbitrary —
   * an Input here, a Select there, occasionally something bespoke. */
  children: (bound: {
    id: string;
    "aria-describedby": string | undefined;
    "aria-invalid": true | undefined;
    required: true | undefined;
  }) => ReactNode;
}

export function Field({ label, hint, required, error, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ");
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {required && (
          <span aria-hidden="true" className={styles.required}>
            *
          </span>
        )}
      </label>
      {children({
        id,
        "aria-describedby": describedBy || undefined,
        "aria-invalid": error ? true : undefined,
        required: required ? true : undefined,
      })}
      {hint && (
        <span className={styles.hint} id={hintId}>
          {hint}
        </span>
      )}
      {error && (
        <span className={styles.error} id={errorId} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

/** `code` switches to the monospace face, for paths, hashes and identifiers. */
type ControlFlavor = "prose" | "code";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "style"> {
  flavor?: ControlFlavor;
  /** Leaves room at the left edge for a glyph the caller positions over it. */
  adorned?: boolean;
  /** `compact` is the shorter box used in dense grids — keyword entry, a
   * contributor's fields — where the full-height control would dominate. */
  density?: "comfortable" | "compact";
}

export function Input({ flavor = "prose", adorned, density, ...rest }: InputProps) {
  return (
    <input
      className={styles.control}
      data-flavor={flavor}
      data-adorned={adorned || undefined}
      data-density={density}
      {...rest}
    />
  );
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "className" | "style"> {
  density?: "comfortable" | "compact";
}

export function Select({ density, ...rest }: SelectProps) {
  return <select className={styles.control} data-density={density} {...rest} />;
}

interface TextareaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className" | "style"> {
  flavor?: ControlFlavor;
}

export function Textarea({ flavor = "prose", ...rest }: TextareaProps) {
  return <textarea className={styles.control} data-flavor={flavor} {...rest} />;
}
