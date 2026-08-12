import { useEffect } from "react";
import { Ic } from "./Icon";
import styles from "./Toast.module.css";

interface ToastProps {
  message: string;
  type: "info" | "success" | "error";
  onClose: () => void;
}

const TOAST_ICON = {
  info: Ic.info,
  success: Ic.check,
  error: Ic.x,
};

export function Toast({ message, type, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className={styles.toast} data-tone={type}>
      <span aria-hidden className={styles.icon}>
        {TOAST_ICON[type](16)}
      </span>
      <span>{message}</span>
      <button type="button" onClick={onClose} aria-label="Dismiss" className={styles.dismiss}>
        {Ic.x(14)}
      </button>
    </div>
  );
}
