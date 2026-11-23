import {
  type InputHTMLAttributes,
  type ReactNode,
  type Ref,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useId,
} from "react";
import styles from "./FormControl.module.css";

interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  error?: ReactNode;
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

type ControlFlavor = "prose" | "code";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "style"> {
  flavor?: ControlFlavor;
  adorned?: boolean;
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
  textareaRef?: Ref<HTMLTextAreaElement>;
}

export function Textarea({ flavor = "prose", textareaRef, ...rest }: TextareaProps) {
  return <textarea ref={textareaRef} className={styles.control} data-flavor={flavor} {...rest} />;
}
