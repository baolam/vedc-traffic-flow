import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  Zap,
  Sliders,
  ShieldCheck,
  ShieldAlert,
  GitCompare,
  Activity,
  Layers,
  ArrowRight,
  TrendingDown,
  Info
} from 'lucide-react';
import { FlowTheorySimulator } from '../utils/flowTheorySimEngine';
import CtmIntersectionCanvas from '../components/algo-demo/CtmIntersectionCanvas';
import FlowTheoryInspector from '../components/algo-demo/FlowTheoryInspector';
import CtmMetricsChart from '../components/algo-demo/CtmMetricsChart';

const FlowTheorySimulationDemo = () => {
  // Simulators
  const [ftSim, setFtSim] = useState(() => new FlowTheorySimulator({ controllerType: 'flow_theory', seed: 42 }));
  const [fixedSim, setFixedSim] = useState(() => new FlowTheorySimulator({ controllerType: 'fixed_time', seed: 42 }));

  // Controls state
  const [isPlaying, setIsPlaying] = useState(true);
  const [simSpeed, setSimSpeed] = useState(1); // 1x, 2x, 5x
  const [isDuelMode, setIsDuelMode] = useState(false);
  const [activeScenario, setActiveScenario] = useState('NORMAL'); // 'NORMAL', 'SPILLBACK', 'RUSH_HOUR'
  const [spillbackActive, setSpillbackActive] = useState(false);
  const [tick, setTick] = useState(0);

  const requestRef = useRef(null);
  const lastTimeRef = useRef(performance.now());

  // Step function
  const stepSim = useCallback((dt) => {
    ftSim.step(dt);
    if (isDuelMode) {
      fixedSim.step(dt);
    }
    setTick(t => t + 1);
  }, [ftSim, fixedSim, isDuelMode]);

  // Main animation / simulation loop
  useEffect(() => {
    if (!isPlaying) return;

    let accumulated = 0;
    const interval = 100 / simSpeed; // 100ms per simulated step scaled by speed

    const timer = setInterval(() => {
      stepSim(0.2); // 0.2s physics step
    }, interval);

    return () => clearInterval(timer);
  }, [isPlaying, simSpeed, stepSim]);

  // Handle Scenario Change
  const handleScenarioChange = (scenario) => {
    setActiveScenario(scenario);
    if (scenario === 'SPILLBACK') {
      ftSim.setDownstreamSpillback(true);
      fixedSim.setDownstreamSpillback(true);
      setSpillbackActive(true);
    } else if (scenario === 'RUSH_HOUR') {
      ftSim.setDownstreamSpillback(false);
      fixedSim.setDownstreamSpillback(false);
      setSpillbackActive(false);
      ftSim.approaches['J1_N_IN'].arrivalRate = 0.55;
      ftSim.approaches['J1_S_IN'].arrivalRate = 0.45;
      fixedSim.approaches['J1_N_IN'].arrivalRate = 0.55;
      fixedSim.approaches['J1_S_IN'].arrivalRate = 0.45;
    } else {
      // Normal
      ftSim.setDownstreamSpillback(false);
      fixedSim.setDownstreamSpillback(false);
      setSpillbackActive(false);
      ftSim.approaches['J1_N_IN'].arrivalRate = 0.28;
      ftSim.approaches['J1_S_IN'].arrivalRate = 0.22;
      fixedSim.approaches['J1_N_IN'].arrivalRate = 0.28;
      fixedSim.approaches['J1_S_IN'].arrivalRate = 0.22;
    }
    setTick(t => t + 1);
  };

  // Toggle Sudden Spillback Button
  const toggleSpillback = () => {
    const next = !spillbackActive;
    setSpillbackActive(next);
    ftSim.setDownstreamSpillback(next);
    fixedSim.setDownstreamSpillback(next);
    setTick(t => t + 1);
  };

  // Reset simulation
  const handleReset = () => {
    ftSim.reset();
    fixedSim.reset();
    setSpillbackActive(false);
    setActiveScenario('NORMAL');
    setTick(t => t + 1);
  };

  return (
    <div className="page-container" style={{ backgroundColor: '#f8fafc', minHeight: '100vh', padding: '24px' }}>
      {/* Page Title & Badges */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px', backgroundColor: '#e0f2fe', color: '#0284c7' }}>
              VEDC ALGORITHM SANDBOX
            </span>
            <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '3px 8px', borderRadius: '6px', backgroundColor: '#fef3c7', color: '#d97706' }}>
              DAGANZO CELL TRANSMISSION MODEL
            </span>
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 900, color: '#0f172a', margin: '6px 0 2px 0' }}>
            Mô Phỏng Thuật Toán FlowTheory (CTM & Anti-Gridlock Gating)
          </h2>
          <p style={{ margin: 0, fontSize: '0.84rem', color: '#64748b' }}>
            Trực quan hóa cân bằng Cung - Cầu, cơ chế bảo vệ ngã tư chống kẹt cứng mạng (Zero-Gridlock) và lan truyền đa bước 2-Hop.
          </p>
        </div>

        {/* Duel Mode Toggle */}
        <button
          onClick={() => setIsDuelMode(!isDuelMode)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '9px 16px',
            borderRadius: '8px',
            backgroundColor: isDuelMode ? '#0284c7' : '#ffffff',
            color: isDuelMode ? '#ffffff' : '#0f172a',
            border: `1px solid ${isDuelMode ? '#0284c7' : '#cbd5e1'}`,
            fontWeight: 800,
            fontSize: '0.85rem',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            transition: 'all 0.2s'
          }}
        >
          <GitCompare size={17} />
          {isDuelMode ? 'Chế Độ Đối Đầu (Duel): BẬT' : 'Bật So Sánh Đối Đầu (vs Fixed-Time)'}
        </button>
      </div>

      {/* Main Control Bar */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        padding: '14px 18px',
        border: '1px solid #e2e8f0',
        marginBottom: '20px',
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '12px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.03)'
      }}>
        {/* Playback Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '6px',
              backgroundColor: isPlaying ? '#fef2f2' : '#f0fdf4',
              color: isPlaying ? '#dc2626' : '#16a34a',
              border: `1px solid ${isPlaying ? '#fecaca' : '#bbf7d0'}`,
              fontWeight: 800,
              fontSize: '0.82rem',
              cursor: 'pointer'
            }}
          >
            {isPlaying ? <Pause size={15} /> : <Play size={15} />}
            {isPlaying ? 'Tạm Dừng' : 'Tiếp Tục'}
          </button>

          <button
            onClick={() => stepSim(1.0)}
            disabled={isPlaying}
            title="Bước tiếp 1 giây (khi tạm dừng)"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#f8fafc',
              color: '#334155',
              border: '1px solid #cbd5e1',
              fontWeight: 700,
              fontSize: '0.82rem',
              cursor: isPlaying ? 'not-allowed' : 'pointer',
              opacity: isPlaying ? 0.6 : 1
            }}
          >
            <SkipForward size={15} /> Bước Tiếp (1s)
          </button>

          <button
            onClick={handleReset}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#f8fafc',
              color: '#64748b',
              border: '1px solid #e2e8f0',
              fontWeight: 600,
              fontSize: '0.82rem',
              cursor: 'pointer'
            }}
          >
            <RotateCcw size={15} /> Đặt Lại
          </button>

          {/* Speed selectors */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '10px' }}>
            <span style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600 }}>Tốc độ:</span>
            {[1, 2, 5].map(spd => (
              <button
                key={spd}
                onClick={() => setSimSpeed(spd)}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: '1px solid',
                  borderColor: simSpeed === spd ? '#0284c7' : '#e2e8f0',
                  backgroundColor: simSpeed === spd ? '#e0f2fe' : '#ffffff',
                  color: simSpeed === spd ? '#0284c7' : '#64748b',
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Traffic Scenario Preset Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#475569' }}>Kịch bản Luồng:</span>
          <select
            value={activeScenario}
            onChange={(e) => handleScenarioChange(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              backgroundColor: '#ffffff',
              fontSize: '0.82rem',
              fontWeight: 600,
              color: '#0f172a'
            }}
          >
            <option value="NORMAL">Giao Thông Bình Thường (Cân Bằng)</option>
            <option value="RUSH_HOUR">Cao Điểm Hướng Bắc-Nam</option>
            <option value="SPILLBACK">Tắc Nghẽn Hạ Lưu J3 (Kiểm chứng Gating)</option>
          </select>

          {/* Quick Spillback Attack Button */}
          <button
            onClick={toggleSpillback}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 12px',
              borderRadius: '6px',
              backgroundColor: spillbackActive ? '#fee2e2' : '#fef3c7',
              color: spillbackActive ? '#dc2626' : '#b45309',
              border: `1px solid ${spillbackActive ? '#fca5a5' : '#fde047'}`,
              fontWeight: 800,
              fontSize: '0.8rem',
              cursor: 'pointer'
            }}
          >
            <Zap size={14} />
            {spillbackActive ? 'Đang Kẹt Hạ Lưu J3 (Tắt)' : '⚡ Kích Hoạt Kẹt Hạ Lưu J3'}
          </button>
        </div>
      </div>

      {/* Main Content Layout */}
      {isDuelMode ? (
        /* DUEL MODE LAYOUT: SIDE-BY-SIDE CANVASES */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            {/* FlowTheory Canvas */}
            <CtmIntersectionCanvas
              sim={ftSim}
              title="1. FLOWTHEORY CONTROLLER"
              subtitle="Cân bằng CTM & Anti-Gridlock Shield (Bảo vệ thông suốt)"
              compact={true}
            />

            {/* Fixed-Time Canvas */}
            <CtmIntersectionCanvas
              sim={fixedSim}
              title="2. FIXED-TIME (BASELINE)"
              subtitle="Chu kỳ đèn cố định (Dễ gây kẹt cứng chữ thập khi hạ lưu tắc)"
              compact={true}
            />
          </div>

          {/* Duel Scoreboard & Metrics */}
          <CtmMetricsChart sim={ftSim} duelSim={fixedSim} isDuelMode={true} />

          {/* Theoretical Inspector */}
          <FlowTheoryInspector sim={ftSim} />
        </div>
      ) : (
        /* SINGLE MODE LAYOUT: CANVAS LEFT + INSPECTOR RIGHT */
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px' }}>
          {/* Left Column: Interactive Canvas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <CtmIntersectionCanvas
              sim={ftSim}
              title="Sa Bàn Nút Giao J1 & Tuyến Hạ Lưu J3"
              subtitle="Điều khiển thời gian thực theo Daganzo Cell Transmission Model"
              compact={false}
            />
            <CtmMetricsChart sim={ftSim} isDuelMode={false} />
          </div>

          {/* Right Column: Mathematical Inspector */}
          <div>
            <FlowTheoryInspector sim={ftSim} />
          </div>
        </div>
      )}
    </div>
  );
};

export default FlowTheorySimulationDemo;
