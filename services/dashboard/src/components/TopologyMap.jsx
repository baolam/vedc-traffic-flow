import React from 'react';
import { useNavigate } from 'react-router-dom';

const TopologyMap = ({ nodesData = {}, onSelectNode }) => {
  const navigate = useNavigate();

  const nodePositions = {
    J1: { x: 180, y: 120, name: "Intersection 1 (North-West)" },
    J2: { x: 520, y: 120, name: "Intersection 2 (North-East)" },
    J3: { x: 180, y: 380, name: "Intersection 3 (South-West)" },
    J4: { x: 520, y: 380, name: "Intersection 4 (South-East)" }
  };

  const edges = [
    { from: "J1", to: "J2", label: "E_J1_J2_EB" },
    { from: "J1", to: "J3", label: "E_J1_J3_SB" },
    { from: "J2", to: "J4", label: "E_J2_J4_SB" },
    { from: "J3", to: "J4", label: "E_J3_J4_EB" }
  ];

  return (
    <div style={{ position: 'relative', width: '100%', height: '500px', backgroundColor: '#0f172a', borderRadius: '12px', border: '1px solid #334155', overflow: 'hidden' }}>
      <svg width="100%" height="100%" viewBox="0 0 700 500">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="25" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
          </marker>
        </defs>

        {/* Draw Edges */}
        {edges.map((edge, idx) => {
          const p1 = nodePositions[edge.from];
          const p2 = nodePositions[edge.to];
          return (
            <g key={idx}>
              <line
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke="#334155"
                strokeWidth="6"
                strokeDasharray="8,4"
              />
              <line
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke="#38bdf8"
                strokeWidth="2"
                opacity="0.8"
                markerEnd="url(#arrow)"
              />
            </g>
          );
        })}

        {/* Draw Nodes */}
        {Object.entries(nodePositions).map(([nodeId, pos]) => {
          const data = nodesData[nodeId] || { current_phase_id: "J1_PHASE_NS", total_queue: 10 };
          const isNS = (data.current_phase_id || "").includes("NS");
          const totalQueue = data.total_queue || Math.floor(Math.random() * 15) + 3;

          return (
            <g
              key={nodeId}
              style={{ cursor: 'pointer' }}
              onClick={() => {
                if (onSelectNode) onSelectNode(nodeId);
                navigate(`/intersections/${nodeId}`);
              }}
            >
              {/* Outer Glow */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r="36"
                fill={isNS ? "rgba(34, 197, 94, 0.15)" : "rgba(56, 189, 248, 0.15)"}
                stroke={isNS ? "#22c55e" : "#38bdf8"}
                strokeWidth="2"
              />

              {/* Node Core */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r="24"
                fill="#1e293b"
              />

              <text
                x={pos.x}
                y={pos.y + 5}
                fill="#f8fafc"
                fontSize="14"
                fontWeight="700"
                textAnchor="middle"
              >
                {nodeId}
              </text>

              {/* Label & Active Phase Badge */}
              <rect
                x={pos.x - 45}
                y={pos.y + 45}
                width="90"
                height="24"
                rx="4"
                fill="#1e293b"
                stroke="#334155"
              />
              <text
                x={pos.x}
                y={pos.y + 61}
                fill="#38bdf8"
                fontSize="11"
                fontWeight="600"
                textAnchor="middle"
              >
                {isNS ? "NS GREEN" : "EW GREEN"}
              </text>

              {/* Queue Badge */}
              <circle cx={pos.x + 26} cy={pos.y - 24} r="12" fill={totalQueue > 12 ? "#ef4444" : "#eab308"} />
              <text x={pos.x + 26} y={pos.y - 20} fill="#ffffff" fontSize="10" fontWeight="700" textAnchor="middle">
                {totalQueue}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default TopologyMap;
