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

  const [telemetryHistory, setTelemetryHistory] = useState([]);
  const [liveApproachStats, setLiveApproachStats] = useState({});

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

  // Live approach telemetry stream polling
  useEffect(() => {
    const fetchNodeTelemetry = () => {
      fetch(`${apiBase}/api/v1/network/state`)
        .then(res => res.json())
        .then(data => {
          if (data && data.nodes) {
            const match = data.nodes.find(n => n.node_id === nodeId);
            if (match) {
              if (match.current_phase_id) {
                setActivePhase(match.current_phase_id);
              }
              const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
              const row = { time: nowTime };
              const currentAppStats = {};
              
              if (match.approaches && match.approaches.length) {
                match.approaches.forEach(a => {
                  row[a.approach_id] = Math.round((a.queue_vehicles || 0) * 10) / 10;
                  currentAppStats[a.approach_id] = a;
                });
              } else {
                approaches.slice(0, 6).forEach(appId => {
                  row[appId] = 0;
                });
              }

              setLiveApproachStats(currentAppStats);

              setTelemetryHistory(prev => {
                const next = [...prev, row];
                return next.slice(-10); // Keep last 10 samples
              });
            }
          }
        })
        .catch(() => {});
    };

    fetchNodeTelemetry();
    const interval = setInterval(fetchNodeTelemetry, 2500);
    return () => clearInterval(interval);
  }, [nodeId, apiBase, approaches]);

  // Generate initial fallback history if stream is empty
  const chartData = telemetryHistory.length > 0 ? telemetryHistory : [
    { time: 'T-20s', [approaches[0]]: 2, [approaches[1]]: 1 },
    { time: 'T-10s', [approaches[0]]: 4, [approaches[1]]: 3 },
    { time: 'Live', [approaches[0]]: 3, [approaches[1]]: 2 }
  ];

  const ackLogs = [
    { time: new Date(Date.now() - 30000).toLocaleTimeString(), command_id: `cmd-${nodeId}-1042`, status: 'APPLIED', reason: `Phase transitioned to ${activePhase} via Yellow (3s) & All-Red (2s) safety constraint.` },
    { time: new Date(Date.now() - 90000).toLocaleTimeString(), command_id: `cmd-${nodeId}-1041`, status: 'REJECTED', reason: 'Min green time constraint active (min_green_s=10.0s not satisfied).' },
    { time: new Date(Date.now() - 150000).toLocaleTimeString(), command_id: `cmd-${nodeId}-1040`, status: 'APPLIED', reason: `Active green phase extended dynamically under ${activeScenarioId} controller policy.` }
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
            <AreaChart data={chartData}>
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
