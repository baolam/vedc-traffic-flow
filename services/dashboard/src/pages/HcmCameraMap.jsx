import React, { useState, useEffect } from 'react';
import { Camera, MapPin, Network, Activity, ExternalLink } from 'lucide-react';

const HcmCameraMap = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total_cameras: 793,
    online_cameras: 793,
    total_edges: 5487,
    topology_id: 'hcm_realworld_v1'
  });

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const mapUrl = `${apiBase}/api/v1/map/hcm-cameras`;

  useEffect(() => {
    fetch(`${apiBase}/api/v1/cameras`)
      .then(res => res.json())
      .then(data => {
        if (data && data.total_cameras) {
          setStats({
            total_cameras: data.total_cameras,
            online_cameras: data.cameras.filter(c => c.status === 'Online').length || data.total_cameras,
            total_edges: data.total_edges,
            topology_id: data.topology_id
          });
        }
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [apiBase]);

  return (
    <div className="page-container">
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, margin: '0 0 6px 0', color: '#0f172a' }}>
            HCM Geographic Camera Map (SUMO Scenario)
          </h2>
          <p style={{ color: '#64748b', margin: 0, fontSize: '0.9rem' }}>
            Real-world traffic camera network graph topology <code style={{ color: '#0284c7', backgroundColor: '#e0f2fe', padding: '2px 6px', borderRadius: '4px' }}>{stats.topology_id}</code> across Ho Chi Minh City.
          </p>
        </div>

        <a
          href={mapUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#ffffff',
            border: '1px solid #cbd5e1',
            color: '#0284c7',
            padding: '8px 16px',
            borderRadius: '8px',
            textDecoration: 'none',
            fontSize: '0.85rem',
            fontWeight: 600,
            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
          }}
        >
          <ExternalLink size={16} /> Open Full Map
        </a>
      </div>

      {/* Top Metric Cards */}
      <div className="grid-cols-4" style={{ marginBottom: '24px' }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(2, 132, 199, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Camera size={24} color="#0284c7" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Cameras</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{stats.total_cameras}</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(22, 163, 74, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <MapPin size={24} color="#16a34a" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Active Nodes</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#16a34a' }}>{stats.online_cameras}</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(202, 138, 4, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Network size={24} color="#ca8a04" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Road Edges</span>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a' }}>{stats.total_edges}</div>
          </div>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ backgroundColor: 'rgba(147, 51, 234, 0.1)', padding: '12px', borderRadius: '10px' }}>
            <Activity size={24} color="#9333ea" />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>SUMO Scenario</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#9333ea' }}>hcm_realworld_v1</div>
          </div>
        </div>
      </div>

      {/* Main Interactive Map Embed */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', height: '620px', position: 'relative' }}>
        <iframe
          title="HCM Geographic Camera Map"
          src={mapUrl}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            backgroundColor: '#f8fafc'
          }}
        />
      </div>
    </div>
  );
};

export default HcmCameraMap;
