import React from 'react';
import TopologyMap from '../components/TopologyMap';
import PhaseIndicator from '../components/PhaseIndicator';
import { Activity, Car, Gauge, Zap } from 'lucide-react';

const NetworkOverview = () => {
  const [nodes, setNodes] = React.useState({
    J1: { current_phase_id: "J1_PHASE_NS", total_queue: 14, speed: 2.1 },
    J2: { current_phase_id: "J2_PHASE_EW", total_queue: 6, speed: 4.8 },
    J3: { current_phase_id: "J3_PHASE_NS", total_queue: 8, speed: 3.2 },
    J4: { current_phase_id: "J4_PHASE_EW", total_queue: 19, speed: 1.5 }
  });

  React.useEffect(() => {
    const interval = setInterval(() => {
      setNodes(prev => {
        const next = { ...prev };
        Object.keys(next).forEach(nodeId => {
          const deltaQueue = Math.floor(Math.random() * 5) - 2;
          const newQueue = Math.max(0, next[nodeId].total_queue + deltaQueue);
          const newSpeed = Math.max(0.5, +(next[nodeId].speed + (Math.random() * 0.6 - 0.3)).toFixed(1));
          const phaseChange = Math.random() < 0.2;
          const currentPhase = next[nodeId].current_phase_id;
          const newPhase = phaseChange 
            ? (currentPhase.includes('NS') ? `${nodeId}_PHASE_EW` : `${nodeId}_PHASE_NS`)
            : currentPhase;

          next[nodeId] = {
            current_phase_id: newPhase,
            total_queue: newQueue,
            speed: newSpeed
          };
        });
        return next;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const totalQueue = Object.values(nodes).reduce((acc, curr) => acc + curr.total_queue, 0);
  const avgSpeed = (Object.values(nodes).reduce((acc, curr) => acc + curr.speed, 0) / Object.keys(nodes).length).toFixed(1);

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 8px 0', color: '#0f172a' }}>Network Topology & Live Traffic State</h2>
        <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
          Real-time Graph State $G_t=(V,E,X_t)$ across 4 interconnected intersections.
        </p>
      </div>

      {/* Top Metric Cards */}
      <div className="grid-cols-4" style={{ marginBottom: '24px' }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(2, 132, 199, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Car size={24} color="#0284c7" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Queue</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{totalQueue} veh</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Gauge size={24} color="#16a34a" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Avg Speed</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{avgSpeed} m/s</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(202, 138, 4, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Zap size={24} color="#ca8a04" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Controller Mode</span>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>Max-Pressure</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Activity size={24} color="#9333ea" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Telemetry Rate</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>10 Hz</div>
          </div>
        </div>
      </div>

      {/* Main Map & Live Intersection Summary */}
      <div className="grid-cols-2">
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', margin: '0 0 16px 0', fontWeight: 700, color: '#0f172a' }}>Interactive Network Topology Map</h3>
          <TopologyMap nodesData={nodes} />
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h3 style={{ fontSize: '1.1rem', margin: '0 0 4px 0', fontWeight: 700, color: '#0f172a' }}>Intersection Live Summary</h3>
          {Object.entries(nodes).map(([nodeId, data]) => (
            <div key={nodeId} style={{
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <span style={{ fontWeight: 700, fontSize: '1rem', color: '#0284c7' }}>{nodeId}</span>
                <span style={{ fontSize: '0.85rem', color: '#64748b', marginLeft: '8px' }}>Queue: {data.total_queue} vehicles</span>
              </div>
              <PhaseIndicator activePhase={data.current_phase_id} state="GREEN" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default NetworkOverview;
