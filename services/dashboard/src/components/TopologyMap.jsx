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
    <div style={{ position: 'relative', width: '100%', height: '500px', backgroundColor: '#f8fafc', borderRadius: '12px', border: '1px solid #cbd5e1', overflow: 'hidden' }}>
      <svg width="100%" height="100%" viewBox="0 0 700 500">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="25" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#0284c7" />
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
                stroke="#cbd5e1"
                strokeWidth="6"
                strokeDasharray="8,4"
              />
              <line
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke="#0284c7"
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
                fill={isNS ? "rgba(22, 163, 74, 0.12)" : "rgba(2, 132, 199, 0.12)"}
                stroke={isNS ? "#16a34a" : "#0284c7"}
                strokeWidth="2"
              />

              {/* Node Core */}
              <circle
                cx={pos.x}
                cy={pos.y}
                r="24"
                fill="#ffffff"
                stroke="#cbd5e1"
                strokeWidth="2"
              />

              <text
                x={pos.x}
                y={pos.y + 5}
                fill="#0f172a"
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
                fill="#ffffff"
                stroke="#cbd5e1"
              />
              <text
                x={pos.x}
                y={pos.y + 61}
                fill={isNS ? "#16a34a" : "#0284c7"}
                fontSize="11"
                fontWeight="700"
                textAnchor="middle"
              >
                {isNS ? "NS GREEN" : "EW GREEN"}
              </text>

              {/* Queue Badge */}
              <circle cx={pos.x + 26} cy={pos.y - 24} r="12" fill={totalQueue > 12 ? "#dc2626" : "#ca8a04"} />
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
