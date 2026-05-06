import { useEffect } from "react";

export function useFocusScroll(focusedField: string | null) {
  useEffect(() => {
    if (!focusedField) return;
    document
      .getElementById(`field-${focusedField}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusedField]);
}
