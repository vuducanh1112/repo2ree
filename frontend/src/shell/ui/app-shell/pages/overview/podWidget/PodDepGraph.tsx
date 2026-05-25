import { C } from "../../../../theme/theme";
import { POD_GRAPHS } from "./podWidgetData";

interface PodDepGraphProps {
  // Dependency-axis level (0..3); selects the dependency-graph illustration.
  level: number;
  color: string;
}

export function PodDepGraph({ level, color }: PodDepGraphProps) {
  if (level === 0)
    return (
      <g opacity="0.3">
        <circle
          cx="0"
          cy="0"
          r="7"
          fill="none"
          stroke="#c8d0dc"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />
      </g>
    );
  const cfg = POD_GRAPHS[level];
  if (!cfg) return null;
  return (
    <g>
      {cfg.edges.map(([a, b]) => {
        const na = cfg.nodes[a],
          nb = cfg.nodes[b];
        return (
          <line
            key={`${a}-${b}`}
            x1={na.x}
            y1={na.y}
            x2={nb.x}
            y2={nb.y}
            stroke={color}
            strokeWidth="1.6"
            opacity="0.38"
          />
        );
      })}
      {cfg.nodes.map((graphNode) => (
        <g key={`${graphNode.x}-${graphNode.y}-${graphNode.r}`}>
          <circle
            cx={graphNode.x}
            cy={graphNode.y}
            r={graphNode.r}
            fill={graphNode.root ? color : C.surface}
            stroke={color}
            strokeWidth={graphNode.root ? 0 : 1.8}
          />
          {graphNode.root && (
            <circle
              cx={graphNode.x}
              cy={graphNode.y}
              r={graphNode.r * 0.38}
              fill="#fff"
              opacity="0.75"
            />
          )}
        </g>
      ))}
    </g>
  );
}
