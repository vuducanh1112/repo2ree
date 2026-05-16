export function expId(index: number) {
  return `EXP-${String(index + 1).padStart(3, "0")}`;
}
