import { 
  Database, 
  FileSpreadsheet, 
  Sparkles, 
  Clock 
} from 'lucide-react';
import type { LineageCanvasNode } from '../../types/navigation';

interface LineageCanvasViewProps {
  canvasNodes: LineageCanvasNode[];
  canvasEdges: { sourceNode: LineageCanvasNode; targetNode: LineageCanvasNode }[];
  selectedNodeId: string | null;
  onSelectNode: (node: LineageCanvasNode) => void;
  width: number;
  height: number;
}

export const LineageCanvasView = ({
  canvasNodes,
  canvasEdges,
  selectedNodeId,
  onSelectNode,
  width,
  height,
}: LineageCanvasViewProps) => {
  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'RAW':
        return {
          border: 'border-blue-500/40',
          selectedBorder: 'border-blue-400 ring-2 ring-blue-500/30',
          badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
          iconBg: 'bg-blue-500/10 text-blue-400',
          accent: '#3b82f6',
          icon: Database
        };
      case 'MAPPED':
        return {
          border: 'border-emerald-500/40',
          selectedBorder: 'border-emerald-400 ring-2 ring-emerald-500/30',
          badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
          iconBg: 'bg-emerald-500/10 text-emerald-400',
          accent: '#10b981',
          icon: FileSpreadsheet
        };
      case 'PRE_PROCESSED':
      default:
        return {
          border: 'border-purple-500/40',
          selectedBorder: 'border-purple-400 ring-2 ring-purple-500/30',
          badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
          iconBg: 'bg-purple-500/10 text-purple-400',
          accent: '#8b5cf6',
          icon: Sparkles
        };
    }
  };

  return (
    <div className="relative w-full h-full min-h-[460px] overflow-auto bg-dark-950 p-6 select-none">
      {/* Background Grid Pattern */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-20"
        style={{
          backgroundImage: `radial-gradient(circle, #334155 1px, transparent 1px)`,
          backgroundSize: '24px 24px'
        }}
      />

      {/* SVG Canvas for Directed Edges (Bezier Curves + Arrows) */}
      <svg 
        className="absolute inset-0 pointer-events-none"
        style={{ width: `${width}px`, height: `${height}px` }}
      >
        <defs>
          <marker
            id="arrowhead-blue"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <polygon points="0 1, 8 4, 0 7" fill="#3b82f6" />
          </marker>
          <marker
            id="arrowhead-emerald"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <polygon points="0 1, 8 4, 0 7" fill="#10b981" />
          </marker>
        </defs>

        {canvasEdges.map((edge, idx) => {
          // Source point (right middle of source node)
          const startX = edge.sourceNode.x + edge.sourceNode.width;
          const startY = edge.sourceNode.y + edge.sourceNode.height / 2;

          // Target point (left middle of target node)
          const endX = edge.targetNode.x;
          const endY = edge.targetNode.y + edge.targetNode.height / 2;

          // Smooth cubic bezier control points
          const dx = (endX - startX) * 0.5;
          const pathD = `M ${startX} ${startY} C ${startX + dx} ${startY}, ${endX - dx} ${endY}, ${endX} ${endY}`;

          const isSourceSelected = edge.sourceNode.id === selectedNodeId;
          const isTargetSelected = edge.targetNode.id === selectedNodeId;
          const isEdgeActive = isSourceSelected || isTargetSelected;

          return (
            <g key={idx}>
              {/* Outer glow stroke when active */}
              {isEdgeActive && (
                <path
                  d={pathD}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth="5"
                  opacity="0.3"
                />
              )}
              {/* Main curve */}
              <path
                d={pathD}
                fill="none"
                stroke={isEdgeActive ? "#3b82f6" : "#334155"}
                strokeWidth={isEdgeActive ? "2.5" : "1.8"}
                strokeDasharray={isEdgeActive ? "none" : "none"}
                markerEnd="url(#arrowhead-emerald)"
                className="transition-all duration-200"
              />
            </g>
          );
        })}
      </svg>

      {/* Render Node Cards on top of SVG */}
      <div 
        className="relative"
        style={{ width: `${width}px`, height: `${height}px` }}
      >
        {canvasNodes.map((node) => {
          const isSelected = selectedNodeId === node.id;
          const theme = getStageColor(node.stage);
          const Icon = theme.icon;

          return (
            <div
              key={node.id}
              onClick={() => onSelectNode(node)}
              style={{
                position: 'absolute',
                left: `${node.x}px`,
                top: `${node.y}px`,
                width: `${node.width}px`,
                height: `${node.height}px`,
              }}
              className={`rounded-xl bg-dark-900 border p-3 cursor-pointer transition-all duration-150 flex flex-col justify-between shadow-lg group hover:scale-[1.02] ${
                isSelected 
                  ? `${theme.selectedBorder} bg-dark-850 shadow-glow-blue z-20` 
                  : `${theme.border} hover:border-slate-500 z-10`
              }`}
            >
              {/* Top row: Icon + Stage Badge + Level */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-lg ${theme.iconBg}`}>
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${theme.badge}`}>
                    {node.stage}
                  </span>
                </div>

                <span className="text-[10px] text-slate-500 font-mono">
                  L{node.level}
                </span>
              </div>

              {/* Bottom row: Artifact ID + Timestamp */}
              <div className="space-y-0.5">
                <div className="text-xs font-mono font-medium text-slate-200 group-hover:text-white truncate">
                  {node.id.slice(0, 14)}...
                </div>
                <div className="flex items-center gap-1 text-[10px] text-slate-500 font-mono">
                  <Clock className="w-2.5 h-2.5" />
                  <span>{new Date(node.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
