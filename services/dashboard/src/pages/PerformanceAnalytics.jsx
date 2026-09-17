import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, LineChart, Line } from 'recharts';
import { Award, Clock, ArrowDownRight, TrendingUp } from 'lucide-react';

const PerformanceAnalytics = () => {
  const benchmarkData = [
    { metric: 'Avg Wait Time (s)', FixedTime: 42.5, MaxPressure: 21.8 },
    { metric: 'Max Queue Length', FixedTime: 28.0, MaxPressure: 14.2 },
    { metric: 'Network Throughput (veh/min)', FixedTime: 110, MaxPressure: 165 }
  ];

  const timeSeriesDelay = [
    { t: '0m', FixedTime: 35, MaxPressure: 20 },
    { t: '5m', FixedTime: 40, MaxPressure: 22 },
    { t: '10m', FixedTime: 48, MaxPressure: 21 },
    { t: '15m', FixedTime: 52, MaxPressure: 23 },
    { t: '20m', FixedTime: 46, MaxPressure: 20 },
    { t: '25m', FixedTime: 43, MaxPressure: 21 }
  ];

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 4px 0' }}>
          Controller Benchmark & Performance Analytics
        </h2>
        <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.9rem' }}>
          Side-by-side performance evaluation: <span style={{ color: '#38bdf8', fontWeight: 600 }}>Max-Pressure Control Policy</span> vs <span style={{ color: '#eab308', fontWeight: 600 }}>Fixed-Time Baseline</span>.
        </p>
      </div>

      {/* Summary Highlight Badges */}
      <div className="grid-cols-4" style={{ marginBottom: '24px' }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)', padding: '12px', borderRadius: '10px' }}>
            <ArrowDownRight size={24} color="#22c55e" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Delay Reduction</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#4ade80' }}>-48.7%</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(56, 189, 248, 0.15)', padding: '12px', borderRadius: '10px' }}>
            <TrendingUp size={24} color="#38bdf8" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Throughput Gain</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#7dd3fc' }}>+50.0%</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(234, 179, 8, 0.15)', padding: '12px', borderRadius: '10px' }}>
            <Clock size={24} color="#eab308" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Avg Delay (MP)</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc' }}>21.8 s</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(168, 85, 247, 0.15)', padding: '12px', borderRadius: '10px' }}>
            <Award size={24} color="#a855f7" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>Optimal Controller</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#c084fc' }}>Max-Pressure</div>
          </div>
        </div>
      </div>

      {/* Comparison Charts */}
      <div className="grid-cols-2">
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 600 }}>
            Key Metrics Comparison
          </h3>
          <div style={{ width: '100%', height: '300px' }}>
            <ResponsiveContainer>
              <BarChart data={benchmarkData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="metric" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }} />
                <Legend />
                <Bar dataKey="FixedTime" fill="#eab308" name="Fixed-Time" />
                <Bar dataKey="MaxPressure" fill="#38bdf8" name="Max-Pressure" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 600 }}>
            Average Wait Time Trend (Minutes)
          </h3>
          <div style={{ width: '100%', height: '300px' }}>
            <ResponsiveContainer>
              <LineChart data={timeSeriesDelay}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="t" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }} />
                <Legend />
                <Line type="monotone" dataKey="FixedTime" stroke="#eab308" strokeWidth={3} name="Fixed-Time" />
                <Line type="monotone" dataKey="MaxPressure" stroke="#38bdf8" strokeWidth={3} name="Max-Pressure" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceAnalytics;
