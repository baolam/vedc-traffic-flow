import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import PhaseIndicator from '../components/PhaseIndicator';

const COLORS = ['#0284c7', '#16a34a', '#ca8a04', '#9333ea', '#dc2626', '#2563eb'];

const IntersectionDetail = () => {
  const { nodeId = 'J1' } = useParams();
  const activeScenarioId = localStorage.getItem('edgeflow_active_scenario') || 'four_intersection_v1';
  
  const [nodeDetail, setNodeDetail] = useState(null);
  const [approaches, setApproaches] = useState([`${nodeId}_N_IN`, `${nodeId}_S_IN`, `${nodeId}_E_IN`, `${nodeId}_W_IN`]);
  const [activePhase, setActivePhase] = useState(`${nodeId}_PHASE_1`);

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetch(`${apiBase}/api/v1/topologies/${activeScenarioId}`)
      .then(res => res.json())
      .then(data => {
        if (data && data.nodes) {
          const match = data.nodes.find(n => n.node_id === nodeId);
          if (match) {
            setNodeDetail(match);
            if (match.approaches && match.approaches.length) {
              setApproaches(match.approaches);
            }
            if (match.phases && match.phases.length) {
              setActivePhase(match.phases[0].phase_id);
            }
          }
        }
      })
      .catch(() => {});
  }, [nodeId, activeScenarioId, apiBase]);

  const mockTimeData = [
    { time: '10:00' },
    { time: '10:01' },
    { time: '10:02' },
    { time: '10:03' },
    { time: '10:04' },
    { time: '10:05' }
  ].map(t => {
    const row = { ...t };
    approaches.slice(0, 6).forEach(app => {
      row[app] = Math.floor(Math.random() * 12) + 1;
    });
    return row;
  });

  const ackLogs = [
    { time: '10:05:12', command_id: 'cmd-9012', status: 'APPLIED', reason: `Safely transitioned to active phase for node ${nodeId} via Yellow (3s) and All-Red (2s).` },
    { time: '10:04:30', command_id: 'cmd-9011', status: 'REJECTED', reason: 'Min green time constraint not met (4.2s < 10.0s)' },
    { time: '10:03:15', command_id: 'cmd-9010', status: 'APPLIED', reason: `Active phase for ${nodeId} extended under Max-Pressure policy.` }
  ];

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 4px 0', color: '#0f172a' }}>
            Intersection Details: <span style={{ color: '#0284c7' }}>{nodeId}</span>
          </h2>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            Scenario: <code style={{ backgroundColor: '#e0f2fe', color: '#0284c7', padding: '2px 6px', borderRadius: '4px' }}>{activeScenarioId}</code> |
            Approaches ({approaches.length}): {approaches.slice(0, 4).join(', ')}{approaches.length > 4 ? '...' : ''}
          </p>
        </div>
        <PhaseIndicator activePhase={activePhase} state="GREEN" />
      </div>

      {/* Queue length chart across approaches */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 700, color: '#0f172a' }}>
          Queue Length Dynamics by Approach ({nodeId})
        </h3>
        <div style={{ width: '100%', height: '300px' }}>
          <ResponsiveContainer>
            <AreaChart data={mockTimeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#cbd5e1', color: '#0f172a' }} />
              {approaches.slice(0, 6).map((app, idx) => (
                <Area
                  key={app}
                  type="monotone"
                  dataKey={app}
                  stackId="1"
                  stroke={COLORS[idx % COLORS.length]}
                  fill={COLORS[idx % COLORS.length]}
                  fillOpacity={0.3}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Actuator Event & ACK History */}
      <div className="card">
        <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 700, color: '#0f172a' }}>
          Actuator ControlACK Event Logs for Node {nodeId}
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #cbd5e1', color: '#64748b' }}>
              <th style={{ padding: '8px 12px' }}>Timestamp</th>
              <th style={{ padding: '8px 12px' }}>Command ID</th>
              <th style={{ padding: '8px 12px' }}>Status</th>
              <th style={{ padding: '8px 12px' }}>Reason / Details</th>
            </tr>
          </thead>
          <tbody>
            {ackLogs.map((log, idx) => (
              <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono', color: '#64748b' }}>{log.time}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono', color: '#0284c7' }}>{log.command_id}</td>
                <td style={{ padding: '10px 12px' }}>
                  <span className={`badge ${log.status === 'APPLIED' ? 'badge-green' : 'badge-red'}`}>
                    {log.status}
                  </span>
                </td>
                <td style={{ padding: '10px 12px', color: '#0f172a' }}>{log.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default IntersectionDetail;
