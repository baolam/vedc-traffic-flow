import React from 'react';
import { useParams } from 'react-router-dom';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import PhaseIndicator from '../components/PhaseIndicator';

const IntersectionDetail = () => {
  const { nodeId = 'J1' } = useParams();

  const mockTimeData = [
    { time: '10:00', North_IN: 8, South_IN: 6, East_IN: 2, West_IN: 1 },
    { time: '10:01', North_IN: 10, South_IN: 9, East_IN: 3, West_IN: 2 },
    { time: '10:02', North_IN: 14, South_IN: 12, East_IN: 1, West_IN: 1 },
    { time: '10:03', North_IN: 5, South_IN: 4, East_IN: 8, West_IN: 7 },
    { time: '10:04', North_IN: 2, South_IN: 3, East_IN: 15, West_IN: 13 },
    { time: '10:05', North_IN: 1, South_IN: 2, East_IN: 11, West_IN: 9 }
  ];

  const ackLogs = [
    { time: '10:05:12', command_id: 'cmd-9012', status: 'APPLIED', reason: 'Safely transitioned to phase J1_PHASE_NS via Yellow (3s) and All-Red (2s).' },
    { time: '10:04:30', command_id: 'cmd-9011', status: 'REJECTED', reason: 'Min green time constraint not met (4.2s < 10.0s)' },
    { time: '10:03:15', command_id: 'cmd-9010', status: 'APPLIED', reason: 'Phase J1_PHASE_EW is already active. Green time extended.' }
  ];

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 4px 0' }}>
            Intersection Details: <span style={{ color: '#38bdf8' }}>{nodeId}</span>
          </h2>
          <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.9rem' }}>
            Approaches: {nodeId}_N_IN, {nodeId}_S_IN, {nodeId}_E_IN, {nodeId}_W_IN
          </p>
        </div>
        <PhaseIndicator activePhase={`${nodeId}_PHASE_NS`} state="GREEN" />
      </div>

      {/* Queue length chart across approaches */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 600 }}>
          Queue Length Dynamics by Approach (Vehicles)
        </h3>
        <div style={{ width: '100%', height: '300px' }}>
          <ResponsiveContainer>
            <AreaChart data={mockTimeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }} />
              <Area type="monotone" dataKey="North_IN" stackId="1" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.3} />
              <Area type="monotone" dataKey="South_IN" stackId="1" stroke="#22c55e" fill="#22c55e" fillOpacity={0.3} />
              <Area type="monotone" dataKey="East_IN" stackId="1" stroke="#eab308" fill="#eab308" fillOpacity={0.3} />
              <Area type="monotone" dataKey="West_IN" stackId="1" stroke="#a855f7" fill="#a855f7" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Actuator Event & ACK History */}
      <div className="card">
        <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 600 }}>
          Actuator ControlACK Event Logs
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
              <th style={{ padding: '8px 12px' }}>Timestamp</th>
              <th style={{ padding: '8px 12px' }}>Command ID</th>
              <th style={{ padding: '8px 12px' }}>Status</th>
              <th style={{ padding: '8px 12px' }}>Reason / Details</th>
            </tr>
          </thead>
          <tbody>
            {ackLogs.map((log, idx) => (
              <tr key={idx} style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono', color: '#94a3b8' }}>{log.time}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'JetBrains Mono', color: '#38bdf8' }}>{log.command_id}</td>
                <td style={{ padding: '10px 12px' }}>
                  <span className={`badge ${log.status === 'APPLIED' ? 'badge-green' : 'badge-red'}`}>
                    {log.status}
                  </span>
                </td>
                <td style={{ padding: '10px 12px', color: '#f8fafc' }}>{log.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default IntersectionDetail;
