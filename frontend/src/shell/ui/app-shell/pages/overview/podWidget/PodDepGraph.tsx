import { C } from "../../../../theme/theme";
import { type LevelMeta, POD_GRAPHS } from "./podWidgetData";

interface PodDepGraphProps {
  level: number;
  levelMeta: LevelMeta;
}

export function PodDepGraph({ level, levelMeta }: PodDepGraphProps) {
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
            stroke={levelMeta.color}
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
            fill={graphNode.root ? levelMeta.color : C.surface}
            stroke={levelMeta.color}
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
