// The pod's machined-metal materials, as references to the roles in tones.css.
// SVG presentation attributes resolve var(), so these go straight into fill and
// stroke without an adapter.
export const POD_M: Record<string, string> = {
  face: "var(--pod-face)",
  raised: "var(--pod-raised)",
  shadow: "var(--pod-shadow)",
  deep: "var(--pod-deep)",
  bolt: "var(--pod-bolt)",
  boltC: "var(--pod-bolt-core)",
  weld: "var(--pod-weld)",
};

interface PodGraphNode {
  x: number;
  y: number;
  r: number;
  root?: boolean;
}
interface PodGraph {
  nodes: PodGraphNode[];
  edges: [number, number][];
}

export const POD_GRAPHS: (PodGraph | null)[] = [
  null,
  { nodes: [{ x: 0, y: 0, r: 7, root: true }], edges: [] },
  {
    nodes: [
      { x: 0, y: -20, r: 7, root: true },
      { x: -17, y: 13, r: 5 },
      { x: 17, y: 13, r: 5 },
    ],
    edges: [
      [0, 1],
      [0, 2],
    ],
  },
  {
    nodes: [
      { x: 0, y: -24, r: 7, root: true },
      { x: -21, y: 0, r: 5 },
      { x: 21, y: 0, r: 5 },
      { x: -12, y: 21, r: 4 },
      { x: 12, y: 21, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 4],
    ],
  },
  {
    nodes: [
      { x: 0, y: -26, r: 7, root: true },
      { x: -23, y: -7, r: 5 },
      { x: 23, y: -7, r: 5 },
      { x: -26, y: 13, r: 4 },
      { x: 0, y: 19, r: 5 },
      { x: 26, y: 13, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 5],
      [1, 4],
      [2, 4],
    ],
  },
  {
    nodes: [
      { x: 0, y: -28, r: 7, root: true },
      { x: -24, y: -11, r: 5 },
      { x: 24, y: -11, r: 5 },
      { x: -30, y: 7, r: 4 },
      { x: -10, y: 15, r: 4 },
      { x: 10, y: 15, r: 4 },
      { x: 30, y: 7, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 4],
      [5, 6],
    ],
  },
  {
    nodes: [
      { x: 0, y: -30, r: 7, root: true },
      { x: -25, y: -13, r: 5 },
      { x: 25, y: -13, r: 5 },
      { x: -32, y: 4, r: 4 },
      { x: -13, y: 9, r: 4 },
      { x: 13, y: 9, r: 4 },
      { x: 32, y: 4, r: 4 },
      { x: 0, y: 26, r: 5 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 7],
      [6, 7],
      [4, 7],
      [5, 7],
    ],
  },
  {
    nodes: [
      { x: 0, y: -32, r: 7, root: true },
      { x: -26, y: -15, r: 5 },
      { x: 26, y: -15, r: 5 },
      { x: -34, y: 2, r: 4 },
      { x: -14, y: 7, r: 4 },
      { x: 14, y: 7, r: 4 },
      { x: 34, y: 2, r: 4 },
      { x: -21, y: 22, r: 4 },
      { x: 0, y: 28, r: 5 },
      { x: 21, y: 22, r: 4 },
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 3],
      [2, 6],
      [1, 4],
      [2, 5],
      [3, 7],
      [6, 9],
      [4, 8],
      [5, 8],
      [7, 8],
      [8, 9],
      [3, 4],
      [5, 6],
    ],
  },
];
