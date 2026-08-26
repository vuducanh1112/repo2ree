import { PAGE } from "@core/app-shell/pages";
import type { NodeOffset } from "@core/canvas/canvasLayout";
import { CANVAS_NODES, type CanvasNode, type CanvasNodeOverview } from "@core/canvas/canvasNodes";
import { fireEvent, render, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NodeCard } from "./NodeCard";

function buildNode(): CanvasNode {
  const found = CANVAS_NODES.find((entry) => entry.key === PAGE.BUILD);
  if (!found) throw new Error("no build node");
  return found;
}

const node = buildNode();

const overview: CanvasNodeOverview = {
  facts: [{ label: "Runtime", value: "image ready" }],
  scripts: [],
  evidenceExpected: false,
  receipt: null,
};

function renderCard(props: Partial<Parameters<typeof NodeCard>[0]> = {}) {
  const onNavigate = vi.fn();
  const onMove = vi.fn();
  const onDraggingChange = vi.fn();
  // Queries scoped to this render's own container: two of these tests mount a
  // second card to compare against the first, and RTL's own bound queries
  // still search the whole document body.
  const view = render(
    <NodeCard
      node={node}
      setRef={() => {}}
      setPortRef={() => {}}
      done={false}
      active={false}
      running={false}
      overview={overview}
      onNavigate={onNavigate}
      offset={{ dx: 0, dy: 0 }}
      zoom={1}
      onMove={onMove}
      onDraggingChange={onDraggingChange}
      {...props}
    />,
  );
  return {
    card: within(view.container).getByRole("button", { name: node.label }),
    onNavigate,
    onMove,
    onDraggingChange,
  };
}

/** A pointer press, some travel, and a release — plus the click the browser
 *  fires afterwards, which is the part that makes drag-vs-click delicate. */
function dragBy(card: HTMLElement, dx: number, dy: number) {
  fireEvent.pointerDown(card, { pointerId: 1, isPrimary: true, button: 0, clientX: 0, clientY: 0 });
  fireEvent.pointerMove(window, { pointerId: 1, clientX: dx, clientY: dy });
  fireEvent.pointerUp(window, { pointerId: 1, clientX: dx, clientY: dy });
  fireEvent.click(card);
}

describe("NodeCard placement", () => {
  const placementOf = (card: HTMLElement) => {
    const anchor = card.closest("[data-floor]");
    if (!(anchor instanceof HTMLElement)) throw new Error("card has no floor anchor");
    return {
      x: anchor.style.getPropertyValue("--node-x"),
      y: anchor.style.getPropertyValue("--node-y"),
    };
  };

  it("stands where the ring puts it when it has not been moved", () => {
    expect(placementOf(renderCard().card)).toEqual({ x: `${node.x}px`, y: `${node.y}px` });
  });

  it("stands where the user put it when it has an offset", () => {
    const { card } = renderCard({ offset: { dx: 120, dy: -40 } });
    expect(placementOf(card)).toEqual({ x: `${node.x + 120}px`, y: `${node.y - 40}px` });
  });
});

describe("NodeCard dragging", () => {
  it("opens the page on a click that did not travel", () => {
    const { card, onNavigate, onMove } = renderCard();
    dragBy(card, 0, 0);
    expect(onNavigate).toHaveBeenCalledWith(PAGE.BUILD, expect.anything());
    expect(onMove).not.toHaveBeenCalled();
  });

  it("still opens the page when the pointer only jitters", () => {
    // A press that shifts a pixel or two is a click by any reasonable reading,
    // and treating it as a drag would make the canvas hard to navigate.
    const { card, onNavigate, onMove } = renderCard();
    dragBy(card, 2, 1);
    expect(onNavigate).toHaveBeenCalled();
    expect(onMove).not.toHaveBeenCalled();
  });

  it("moves the panel instead of navigating once the pointer travels", () => {
    const { card, onNavigate, onMove } = renderCard();
    dragBy(card, 60, 30);
    expect(onNavigate).not.toHaveBeenCalled();
    expect(onMove).toHaveBeenCalledTimes(1);
    const [key, offset] = onMove.mock.calls[0] as [string, NodeOffset];
    expect(key).toBe(PAGE.BUILD);
    expect(offset.dx).toBeGreaterThan(0);
  });

  it("navigates again on the next plain click after a drag", () => {
    // The swallow is armed for exactly one click, not left latched.
    const { card, onNavigate } = renderCard();
    dragBy(card, 60, 30);
    expect(onNavigate).not.toHaveBeenCalled();
    fireEvent.click(card);
    expect(onNavigate).toHaveBeenCalledTimes(1);
  });

  it("announces the drag so the canvas can keep the cables measured", () => {
    const { card, onDraggingChange } = renderCard();
    dragBy(card, 60, 30);
    expect(onDraggingChange).toHaveBeenNthCalledWith(1, PAGE.BUILD, true);
    expect(onDraggingChange).toHaveBeenLastCalledWith(PAGE.BUILD, false);
  });

  it("commits nothing when the gesture is cancelled mid-drag", () => {
    const { card, onMove } = renderCard();
    fireEvent.pointerDown(card, {
      pointerId: 1,
      isPrimary: true,
      button: 0,
      clientX: 0,
      clientY: 0,
    });
    fireEvent.pointerMove(window, { pointerId: 1, clientX: 60, clientY: 30 });
    fireEvent.pointerCancel(window, { pointerId: 1 });
    expect(onMove).not.toHaveBeenCalled();
  });

  it("ignores a secondary button", () => {
    const { card, onMove } = renderCard();
    fireEvent.pointerDown(card, {
      pointerId: 1,
      isPrimary: true,
      button: 2,
      clientX: 0,
      clientY: 0,
    });
    fireEvent.pointerMove(window, { pointerId: 1, clientX: 60, clientY: 30 });
    fireEvent.pointerUp(window, { pointerId: 1, clientX: 60, clientY: 30 });
    expect(onMove).not.toHaveBeenCalled();
  });

  it("reads the drag through the camera's zoom", () => {
    // The same gesture at half zoom covers twice as much bench.
    const near = renderCard({ zoom: 2 });
    dragBy(near.card, 100, 0);
    const far = renderCard({ zoom: 0.5 });
    dragBy(far.card, 100, 0);
    const nearOffset = (near.onMove.mock.calls[0] as [string, NodeOffset])[1];
    const farOffset = (far.onMove.mock.calls[0] as [string, NodeOffset])[1];
    expect(Math.abs(farOffset.dx)).toBeGreaterThan(Math.abs(nearOffset.dx));
  });
});

describe("NodeCard keyboard placement", () => {
  // Dragging is a pointer gesture; WCAG 2.2 asks that what it does also be
  // reachable without one.
  it("moves the focused panel with the arrow keys", () => {
    const { card, onMove } = renderCard();
    fireEvent.keyDown(card, { key: "ArrowRight" });
    const [key, offset] = onMove.mock.calls[0] as [string, NodeOffset];
    expect(key).toBe(PAGE.BUILD);
    expect(offset.dx).toBeGreaterThan(0);
  });

  it("moves further with shift held", () => {
    const small = renderCard();
    fireEvent.keyDown(small.card, { key: "ArrowRight" });
    const large = renderCard();
    fireEvent.keyDown(large.card, { key: "ArrowRight", shiftKey: true });
    const a = (small.onMove.mock.calls[0] as [string, NodeOffset])[1];
    const b = (large.onMove.mock.calls[0] as [string, NodeOffset])[1];
    expect(b.dx).toBeGreaterThan(a.dx);
  });

  it("leaves keys that are not arrows to the button", () => {
    const { card, onMove } = renderCard();
    fireEvent.keyDown(card, { key: "Enter" });
    expect(onMove).not.toHaveBeenCalled();
  });
});
