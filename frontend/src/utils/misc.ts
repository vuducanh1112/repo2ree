export function triggerOnEnterOrSpace(
  event: React.KeyboardEvent<HTMLElement>,
  action: () => void,
): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}
