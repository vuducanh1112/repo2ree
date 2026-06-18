import { C } from "../../theme/theme";

/** 7px indicator dot used on canvas HUD consoles and node cards. */
export function StatusDot({ on }: { on: boolean }) {
  return (
    <span
      style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        flexShrink: 0,
        background: on ? C.done : C.borderMid,
        boxShadow: on ? `0 0 7px ${C.done}88` : "none",
      }}
    />
  );
}
