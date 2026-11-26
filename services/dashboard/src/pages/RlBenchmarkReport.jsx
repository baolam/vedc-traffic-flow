import React, { useState, useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  Cell,
  LineChart,
  Line
} from 'recharts';
import {
  Brain,
  Award,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldCheck,
  TrendingDown,
  Layers,
  Activity,
  Cpu,
  Info,
  Sparkles,
  GitCompare,
  FileText
} from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';
import rlData from '../data/rl_benchmark_report_20261126.json';

const COPY = {
  en: {
    pageTitle: 'RL Application Benchmark Report (2026-11-26)',
    subtitle: 'Comprehensive evaluation of Deep Reinforcement Learning (Phase DQN & EdgeFlow RL Two-Tier Residual) vs Deterministic Baselines on 20 held-out evaluation seeds.',
    badgeHeldOut: 'Held-Out Test Seeds: 80001–80020',
    badgeTotalRuns: '10,440 Simulation Runs',
    kpiOverallRank: 'Best Overall Controller',
    kpiOverallDesc: 'EdgeFlow RL leads with 0.725–0.749 relative delay vs 0.751 for best deterministic.',
    kpiGatePromotion: 'Research Gate Promotion',
    kpiGateDesc: 'Jakarta promoted (5/5 seeds), Hanoi (seed 2026). Strongest gain vs plain baselines.',
    kpiSeedStability: 'Policy Robustness (Low Variance)',
    kpiSeedDesc: 'Learner seed sd ≤ 0.8s on 5/6 maps. Residual anchor prevents policy drift.',
    kpiSafetyEnvelope: 'Max-Red 40s Safety Envelope',
    kpiSafetyDesc: 'Eliminates catastrophic gridlock in Hanoi (339s → 51s) & Grid4x4 (450s → 21s).',
    tabCharts: 'Visual Analytics & Comparisons',
    tabBreakdown: 'Map-by-Map Performance & Cases',
    tabQualification: 'Research Qualification Gate',
    tabArchitecture: 'Architecture & Engineering Lessons',
    chartMeanDelay: 'Mean Delay by Map (s)',
    chartRelativeDelay: 'Relative Delay vs Tuned Fixed-Time',
    chartSeedVariance: 'Seed Stability: EdgeFlow RL vs Free DQN',
    chartVehicleClass: 'Vehicle Class Delay (Hanoi)',
    filterMap: 'Select Network Map:',
    filterAll: 'All Networks',
    colMap: 'Map / Network',
    colFixedTime: 'Fixed-Time (Ref)',
    colActuated: 'Actuated',
    colMaxPressure: 'Max-Pressure (+MR)',
    colFlowTheory: 'FlowTheory (+MR)',
    colBaselineDqn: 'Phase DQN Baseline',
    colConfigC: 'EdgeFlow RL (Residual RL)',
    colVerdict: 'Status & Paired Verdict',
    guardrailPass: 'Guardrail Passed',
    guardrailFail: 'Guardrail Failed',
    guardrailWarning: 'Tail Regressions',
    promotedBadge: 'PROMOTED',
    blockedBadge: 'BLOCKED',
    legendFixedTime: 'Fixed-Time (Reference)',
    legendMaxPressure: 'Max-Pressure + Max-Red',
    legendFlowTheory: 'FlowTheory + Max-Red',
    legendPhaseDqn: 'Phase DQN Baseline',
    legendConfigC: 'EdgeFlow RL (Residual DQN)',
    takeawayTitle: 'Key Takeaways & Production Insights'
  },
  vi: {
    pageTitle: 'Báo Cáo Đánh Giá Thực Nghiệm Ứng Dụng RL (2026-11-26)',
    subtitle: 'Thực nghiệm chuyên sâu đánh giá mô hình Học Tăng Cường (Phase DQN & EdgeFlow RL hai tầng) so với các bộ điều khiển tất định trên 20 seed kiểm định độc lập.',
    badgeHeldOut: '20 Seed Độc Lập: 80001–80020',
    badgeTotalRuns: '10,440 Lượt Chạy Mô Phỏng SUMO',
    kpiOverallRank: 'Thuật Toán Dẫn Đầu Toàn Diện',
    kpiOverallDesc: 'EdgeFlow RL đạt độ trễ tương đối 0.725–0.749 so với 0.751 của FlowTheory và 1.000 của Fixed-Time.',
    kpiGatePromotion: 'Cổng Thẩm Định Nghiên Cứu',
    kpiGateDesc: 'Jakarta được thông qua (5/5 seed), Hà Nội (seed 2026). Tăng trưởng +24% so với Max-Pressure.',
    kpiSeedStability: 'Độ Ổn Định & Kháng Nhiễu Seed',
    kpiSeedDesc: 'Độ lệch chuẩn learner seed ≤ 0.8s trên 5/6 bản đồ. Khắc phục triệt để biến động của RL thuần.',
    kpiSafetyEnvelope: 'Lưới An Toàn Max-Red 40s',
    kpiSafetyDesc: 'Chặn đứng kẹt cứng (gridlock) tại Hà Nội (từ 339s xuống 51s) và Grid4x4 (từ 450s xuống 21s).',
    tabCharts: 'Biểu Đồ Trực Quan & So Sánh',
    tabBreakdown: 'Chi Tiết Từng Bản Đồ & Kịch Bản',
    tabQualification: 'Cổng Thẩm Định (Qualification Gate)',
    tabArchitecture: 'Kiến Trúc & Bài Học Kỹ Thuật',
    chartMeanDelay: 'Độ Trễ Trung Bình Theo Bản Đồ (giây)',
    chartRelativeDelay: 'Tỉ Lệ Độ Trễ So Với Fixed-Time Chuẩn',
    chartSeedVariance: 'Độ Ổn Định Seed: EdgeFlow RL vs Free DQN',
    chartVehicleClass: 'Độ Trễ Theo Phân Lớp Phương Tiện (Hà Nội)',
    filterMap: 'Chọn Bản Đồ Mạng Lưới:',
    filterAll: 'Tất Cả Bản Đồ',
    colMap: 'Mạng Lưới Giao Thông',
    colFixedTime: 'Fixed-Time (Chuẩn)',
    colActuated: 'Actuated',
    colMaxPressure: 'Max-Pressure (+MR)',
    colFlowTheory: 'FlowTheory (+MR)',
    colBaselineDqn: 'Phase DQN Cơ Bản',
    colConfigC: 'EdgeFlow RL (Residual RL)',
    colVerdict: 'Kết Quả Thẩm Định',
    guardrailPass: 'Đạt Chuẩn An Toàn',
    guardrailFail: 'Vi Phạm Chuẩn',
    guardrailWarning: 'Cảnh Báo Đuôi Đợi',
    promotedBadge: 'ĐƯỢC DUYỆT',
    blockedBadge: 'BỊ CHẶN',
    legendFixedTime: 'Fixed-Time (Chuẩn Cơ Sở)',
    legendMaxPressure: 'Max-Pressure + Max-Red',
    legendFlowTheory: 'FlowTheory + Max-Red',
    legendPhaseDqn: 'Phase DQN Baseline (Tự Do)',
    legendConfigC: 'EdgeFlow RL (Học Tăng Cường Residual)',
    takeawayTitle: 'Tổng Kết & Khuyến Nghị Triển Khai Thực Tế'
  }
};

const CHART_PALETTE = {
  fixed_time: '#94a3b8',
  max_pressure: '#0284c7',
  flow_theory: '#10b981',
  phase_dqn: '#f59e0b',
  config_c: '#8b5cf6'
};

const RlBenchmarkReport = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.vi;

  const [activeMainTab, setActiveMainTab] = useState('charts'); // charts, breakdown, qualification, architecture
  const [selectedChartType, setSelectedChartType] = useState('mean_delay'); // mean_delay, relative_delay, seed_variance, vehicle_class
  const [selectedMapFilter, setSelectedMapFilter] = useState('ALL');

  // Format bar chart data for mean delay
  const barChartData = useMemo(() => {
    return rlData.map_scores.map((item) => ({
      name: item.map,
      fullName: item.map_name,
      'Fixed-Time': item.fixed_time.score,
      'Max-Pressure (+MR)': item.max_pressure_mr.score,
      'FlowTheory (+MR)': item.flow_theory_mr.score,
      'Phase DQN Baseline': item.phase_dqn_baseline.score,
      'EdgeFlow RL': item.round3_config_c.score
    }));
  }, []);

  // Filtered maps for the detailed performance section
  const displayedMaps = useMemo(() => {
    if (selectedMapFilter === 'ALL') {
      return rlData.map_scores;
    }
    return rlData.map_scores.filter((m) => m.map === selectedMapFilter);
  }, [selectedMapFilter]);

  return (
    <div className="page-container" style={{ paddingBottom: '48px' }}>
      {/* 1. Header Section */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '24px',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <div style={{
              backgroundColor: '#f5f3ff',
              border: '1px solid #ddd6fe',
              color: '#7c3aed',
              padding: '6px 10px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 700,
              fontSize: '0.85rem'
            }}>
              <Brain size={18} />
              <span>RL Benchmark Suite 2026-11-26</span>
            </div>
            <span className="badge badge-green" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CheckCircle2 size={13} /> {t.badgeHeldOut}
            </span>
            <span className="badge badge-blue">
              {t.badgeTotalRuns}
            </span>
          </div>
          <h1 style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0f172a', margin: '0 0 6px 0' }}>
            {t.pageTitle}
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.9rem', maxWidth: '900px', margin: 0, lineHeight: 1.5 }}>
            {t.subtitle}
          </p>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          backgroundColor: '#ffffff',
          padding: '8px 14px',
          borderRadius: '10px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)'
        }}>
          <FileText size={18} style={{ color: '#6366f1' }} />
          <div>
            <div style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700 }}>
              Report Source
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155' }}>
              experiments/TEST_BENCHMARK_REPORT_20261126.md
            </div>
          </div>
        </div>
      </div>

      {/* 2. Executive KPI Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        {/* KPI 1 */}
        <div className="card" style={{ borderLeft: '4px solid #8b5cf6' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              {t.kpiOverallRank}
            </span>
            <Award size={18} style={{ color: '#8b5cf6' }} />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#1e1b4b', marginBottom: '4px' }}>
            EdgeFlow RL (0.725x)
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.4 }}>
            {t.kpiOverallDesc}
          </div>
        </div>

        {/* KPI 2 */}
        <div className="card" style={{ borderLeft: '4px solid #10b981' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              {t.kpiGatePromotion}
            </span>
            <CheckCircle2 size={18} style={{ color: '#10b981' }} />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#064e3b', marginBottom: '4px' }}>
            Jakarta + Hanoi (Seed 2026)
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.4 }}>
            {t.kpiGateDesc}
          </div>
        </div>

        {/* KPI 3 */}
        <div className="card" style={{ borderLeft: '4px solid #0284c7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              {t.kpiSeedStability}
            </span>
            <Activity size={18} style={{ color: '#0284c7' }} />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#0c4a6e', marginBottom: '4px' }}>
            Learner SD ≤ 0.8s
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.4 }}>
            {t.kpiSeedDesc}
          </div>
        </div>

        {/* KPI 4 */}
        <div className="card" style={{ borderLeft: '4px solid #f59e0b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              {t.kpiSafetyEnvelope}
            </span>
            <ShieldCheck size={18} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#78350f', marginBottom: '4px' }}>
            Zero Urban Gridlock
          </div>
          <div style={{ fontSize: '0.8rem', color: '#475569', lineHeight: 1.4 }}>
            {t.kpiSafetyDesc}
          </div>
        </div>
      </div>

      {/* 3. Main Navigation Tabs */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid #e2e8f0',
        marginBottom: '24px',
        gap: '8px',
        overflowX: 'auto'
      }}>
        <button
          onClick={() => setActiveMainTab('charts')}
          style={{
            padding: '10px 18px',
            border: 'none',
            borderBottom: activeMainTab === 'charts' ? '3px solid #8b5cf6' : '3px solid transparent',
            backgroundColor: 'transparent',
            color: activeMainTab === 'charts' ? '#7c3aed' : '#64748b',
            fontWeight: activeMainTab === 'charts' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <TrendingDown size={16} />
          {t.tabCharts}
        </button>

        <button
          onClick={() => setActiveMainTab('breakdown')}
          style={{
            padding: '10px 18px',
            border: 'none',
            borderBottom: activeMainTab === 'breakdown' ? '3px solid #8b5cf6' : '3px solid transparent',
            backgroundColor: 'transparent',
            color: activeMainTab === 'breakdown' ? '#7c3aed' : '#64748b',
            fontWeight: activeMainTab === 'breakdown' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Layers size={16} />
          {t.tabBreakdown}
        </button>

        <button
          onClick={() => setActiveMainTab('qualification')}
          style={{
            padding: '10px 18px',
            border: 'none',
            borderBottom: activeMainTab === 'qualification' ? '3px solid #8b5cf6' : '3px solid transparent',
            backgroundColor: 'transparent',
            color: activeMainTab === 'qualification' ? '#7c3aed' : '#64748b',
            fontWeight: activeMainTab === 'qualification' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <ShieldCheck size={16} />
          {t.tabQualification}
        </button>

        <button
          onClick={() => setActiveMainTab('architecture')}
          style={{
            padding: '10px 18px',
            border: 'none',
            borderBottom: activeMainTab === 'architecture' ? '3px solid #8b5cf6' : '3px solid transparent',
            backgroundColor: 'transparent',
            color: activeMainTab === 'architecture' ? '#7c3aed' : '#64748b',
            fontWeight: activeMainTab === 'architecture' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Cpu size={16} />
          {t.tabArchitecture}
        </button>
      </div>

      {/* TAB CONTENT 1: VISUAL CHARTS */}
      {activeMainTab === 'charts' && (
        <div>
          {/* Sub tabs for charts */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setSelectedChartType('mean_delay')}
              className="btn"
              style={{
                backgroundColor: selectedChartType === 'mean_delay' ? '#f5f3ff' : '#ffffff',
                border: selectedChartType === 'mean_delay' ? '1px solid #c4b5fd' : '1px solid #e2e8f0',
                color: selectedChartType === 'mean_delay' ? '#6d28d9' : '#475569',
                fontWeight: 600,
                fontSize: '0.85rem',
                borderRadius: '8px',
                padding: '6px 14px'
              }}
            >
              {t.chartMeanDelay}
            </button>

            <button
              onClick={() => setSelectedChartType('relative_delay')}
              className="btn"
              style={{
                backgroundColor: selectedChartType === 'relative_delay' ? '#f5f3ff' : '#ffffff',
                border: selectedChartType === 'relative_delay' ? '1px solid #c4b5fd' : '1px solid #e2e8f0',
                color: selectedChartType === 'relative_delay' ? '#6d28d9' : '#475569',
                fontWeight: 600,
                fontSize: '0.85rem',
                borderRadius: '8px',
                padding: '6px 14px'
              }}
            >
              {t.chartRelativeDelay}
            </button>

            <button
              onClick={() => setSelectedChartType('seed_variance')}
              className="btn"
              style={{
                backgroundColor: selectedChartType === 'seed_variance' ? '#f5f3ff' : '#ffffff',
                border: selectedChartType === 'seed_variance' ? '1px solid #c4b5fd' : '1px solid #e2e8f0',
                color: selectedChartType === 'seed_variance' ? '#6d28d9' : '#475569',
                fontWeight: 600,
                fontSize: '0.85rem',
                borderRadius: '8px',
                padding: '6px 14px'
              }}
            >
              {t.chartSeedVariance}
            </button>

            <button
              onClick={() => setSelectedChartType('vehicle_class')}
              className="btn"
              style={{
                backgroundColor: selectedChartType === 'vehicle_class' ? '#f5f3ff' : '#ffffff',
                border: selectedChartType === 'vehicle_class' ? '1px solid #c4b5fd' : '1px solid #e2e8f0',
                color: selectedChartType === 'vehicle_class' ? '#6d28d9' : '#475569',
                fontWeight: 600,
                fontSize: '0.85rem',
                borderRadius: '8px',
                padding: '6px 14px'
              }}
            >
              {t.chartVehicleClass}
            </button>
          </div>

          {/* Chart Display Container */}
          <div className="card" style={{ marginBottom: '24px' }}>
            {selectedChartType === 'mean_delay' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <div>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 4px 0', color: '#1e293b' }}>
                      {lang === 'vi' ? 'Độ Trễ Trung Bình (s) Qua 6 Mạng Lưới - 20 Held-Out Seeds' : 'Mean Delay per Vehicle (s) Across 6 Benchmark Networks (20 Test Seeds)'}
                    </h3>
                    <p style={{ fontSize: '0.8rem', color: '#64748b', margin: 0 }}>
                      {lang === 'vi' ? 'Giá trị càng thấp càng tốt. So sánh Fixed-Time, Max-Pressure (+MR), FlowTheory (+MR), Phase DQN cơ bản và EdgeFlow RL.' : 'Lower is better. Comparing Fixed-Time, Max-Pressure (+MR), FlowTheory (+MR), Phase DQN baseline, and EdgeFlow RL.'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      backgroundColor: '#f1f5f9',
                      border: '1px solid #cbd5e1',
                      color: '#1e293b',
                      fontWeight: 700,
                      fontSize: '0.8rem'
                    }}>
                      <span style={{ width: '10px', height: '10px', backgroundColor: CHART_PALETTE.fixed_time, borderRadius: '2px', display: 'inline-block' }}></span>
                      <span>{t.legendFixedTime}</span>
                    </div>

                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      backgroundColor: '#f0f9ff',
                      border: '1px solid #bae6fd',
                      color: '#0369a1',
                      fontWeight: 700,
                      fontSize: '0.8rem'
                    }}>
                      <span style={{ width: '10px', height: '10px', backgroundColor: CHART_PALETTE.max_pressure, borderRadius: '2px', display: 'inline-block' }}></span>
                      <span>{t.legendMaxPressure}</span>
                    </div>

                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      backgroundColor: '#ecfdf5',
                      border: '1px solid #a7f3d0',
                      color: '#065f46',
                      fontWeight: 700,
                      fontSize: '0.8rem'
                    }}>
                      <span style={{ width: '10px', height: '10px', backgroundColor: CHART_PALETTE.flow_theory, borderRadius: '2px', display: 'inline-block' }}></span>
                      <span>{t.legendFlowTheory}</span>
                    </div>

                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      backgroundColor: '#fffbeb',
                      border: '1px solid #fde68a',
                      color: '#92400e',
                      fontWeight: 700,
                      fontSize: '0.8rem'
                    }}>
                      <span style={{ width: '10px', height: '10px', backgroundColor: CHART_PALETTE.phase_dqn, borderRadius: '2px', display: 'inline-block' }}></span>
                      <span>{t.legendPhaseDqn}</span>
                    </div>

                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      backgroundColor: '#f5f3ff',
                      border: '1px solid #ddd6fe',
                      color: '#6d28d9',
                      fontWeight: 800,
                      fontSize: '0.8rem'
                    }}>
                      <span style={{ width: '10px', height: '10px', backgroundColor: CHART_PALETTE.config_c, borderRadius: '2px', display: 'inline-block' }}></span>
                      <span>{t.legendConfigC}</span>
                    </div>
                  </div>
                </div>

                <div style={{ height: '380px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barChartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#475569', fontSize: 12 }} unit="s" />
                      <Tooltip
                        formatter={(val) => [`${val.toFixed(1)} s`, 'Delay']}
                        contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #cbd5e1', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}
                      />
                      <Legend wrapperStyle={{ color: '#1e293b', paddingTop: '12px', fontSize: '0.85rem', fontWeight: 600 }} />
                      <Bar dataKey="Fixed-Time" fill={CHART_PALETTE.fixed_time} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="Max-Pressure (+MR)" fill={CHART_PALETTE.max_pressure} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="FlowTheory (+MR)" fill={CHART_PALETTE.flow_theory} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="Phase DQN Baseline" fill={CHART_PALETTE.phase_dqn} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="EdgeFlow RL" fill={CHART_PALETTE.config_c} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {selectedChartType === 'relative_delay' && (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 4px 0', color: '#1e293b' }}>
                    {lang === 'vi' ? 'Độ Trễ Tương Đối Bình Quân So Với Tuned Fixed-Time (Reference = 1.000)' : 'Equal-Map Aggregate Relative Delay vs Tuned Fixed-Time (Reference = 1.000)'}
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: '#64748b', margin: 0 }}>
                    {lang === 'vi' ? 'Giá trị < 1.0 biểu thị mức cải thiện so với Fixed-Time. EdgeFlow RL đạt 0.725–0.749 (dẫn đầu toàn bộ thuật toán).' : 'Values < 1.0 indicate delay reduction vs baseline. EdgeFlow RL reaches 0.725–0.749 (overall benchmark champion).'}
                  </p>
                </div>

                <div style={{ height: '420px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={rlData.relative_delay_comparison}
                      margin={{ top: 10, right: 30, left: 180, bottom: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                      <XAxis type="number" domain={[0, 4.0]} tick={{ fill: '#475569', fontSize: 12 }} />
                      <YAxis
                        type="category"
                        dataKey="controller"
                        tick={{ fill: '#334155', fontSize: 11, fontWeight: 500 }}
                        width={170}
                      />
                      <Tooltip
                        formatter={(val) => [`${val.toFixed(3)}x Fixed-Time`, 'Relative Delay']}
                        contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                      />
                      <Bar dataKey="relative_delay" radius={[0, 4, 4, 0]}>
                        {rlData.relative_delay_comparison.map((entry, index) => {
                          let color = '#94a3b8';
                          if (entry.category === 'Learned RL') color = entry.controller.includes('EdgeFlow RL') ? '#8b5cf6' : '#f59e0b';
                          else if (entry.category === 'Deterministic') color = entry.relative_delay > 1.5 ? '#ef4444' : '#0284c7';
                          else if (entry.category === 'Baseline') color = '#64748b';
                          return <Cell key={`cell-${index}`} fill={color} />;
                        })}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {selectedChartType === 'seed_variance' && (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 4px 0', color: '#1e293b' }}>
                    {lang === 'vi' ? 'Độ Lệch Chuẩn & Biến Thiên Qua 5 Learner Seeds (Jakarta & Hà Nội)' : 'Learner Seed Stability: EdgeFlow RL vs Free Phase DQN Baseline'}
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: '#64748b', margin: 0 }}>
                    {lang === 'vi' ? 'EdgeFlow RL đạt đường trễ phẳng tuyệt đối tại Jakarta (23.9s) và Hà Nội (27.9s–32.5s), trong khi Free DQN dao động mạnh tới 13.5s độ lệch chuẩn.' : 'EdgeFlow RL displays near-zero seed variance due to its residual structure, whereas Free DQN suffers massive exploratory divergence.'}
                  </p>
                </div>

                <div style={{ height: '360px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={rlData.seed_variance} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="seed" tick={{ fill: '#475569', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#475569', fontSize: 12 }} unit="s" domain={[15, 80]} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                      />
                      <Legend />
                      <Line type="monotone" dataKey="baseline_hanoi" name="Hanoi: Free DQN Baseline" stroke="#f59e0b" strokeWidth={3} strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="config_c_hanoi" name="Hanoi: EdgeFlow RL" stroke="#8b5cf6" strokeWidth={3} />
                      <Line type="monotone" dataKey="baseline_jakarta" name="Jakarta: Free DQN Baseline" stroke="#94a3b8" strokeWidth={2} strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="config_c_jakarta" name="Jakarta: EdgeFlow RL" stroke="#10b981" strokeWidth={3} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {selectedChartType === 'vehicle_class' && (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 4px 0', color: '#1e293b' }}>
                    {lang === 'vi' ? 'Độ Trễ Theo Phân Lớp Phương Tiện Tại Mạng Lưới Hà Nội' : 'Per-Vehicle Class Delay on Hanoi Network (Motorcycle, Car, Taxi, Bus, Truck)'}
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: '#64748b', margin: 0 }}>
                    {lang === 'vi' ? 'Đánh giá tính công bằng (fairness): EdgeFlow RL giảm độ trễ đồng đều cho mọi phương tiện (từ xe máy, ô tô con đến xe buýt công cộng).' : 'Fairness analysis: EdgeFlow RL reduces delay uniformly across motorcycles, passenger cars, taxis, buses, and heavy trucks.'}
                  </p>
                </div>

                <div style={{ height: '360px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={rlData.vehicle_class_delays} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="class" tick={{ fill: '#475569', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#475569', fontSize: 12 }} unit="s" />
                      <Tooltip
                        formatter={(val) => [`${val.toFixed(1)} s`, 'Delay']}
                        contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                      />
                      <Legend />
                      <Bar dataKey="fixed_time" name="Fixed-Time" fill="#94a3b8" />
                      <Bar dataKey="actuated" name="Actuated" fill="#ef4444" />
                      <Bar dataKey="max_pressure_mr" name="Max-Pressure + MR" fill="#0284c7" />
                      <Bar dataKey="flow_theory_mr" name="FlowTheory + MR" fill="#10b981" />
                      <Bar dataKey="config_c" name="EdgeFlow RL" fill="#8b5cf6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB CONTENT 2: MAP BREAKDOWN & WORKLOAD CASES */}
      {activeMainTab === 'breakdown' && (
        <div>
          {/* Map filter selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#475569' }}>
              {t.filterMap}
            </span>
            <button
              onClick={() => setSelectedMapFilter('ALL')}
              className="btn"
              style={{
                backgroundColor: selectedMapFilter === 'ALL' ? '#8b5cf6' : '#ffffff',
                color: selectedMapFilter === 'ALL' ? '#ffffff' : '#475569',
                border: '1px solid #cbd5e1',
                padding: '4px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                fontWeight: 600
              }}
            >
              {t.filterAll}
            </button>
            {rlData.maps.map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedMapFilter(m.id)}
                className="btn"
                style={{
                  backgroundColor: selectedMapFilter === m.id ? '#8b5cf6' : '#ffffff',
                  color: selectedMapFilter === m.id ? '#ffffff' : '#475569',
                  border: '1px solid #cbd5e1',
                  padding: '4px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  fontWeight: 600
                }}
              >
                {m.name} ({m.junctions} Junc)
              </button>
            ))}
          </div>

          {/* Cards for each map */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {displayedMaps.map((mapItem) => (
              <div key={mapItem.map} className="card" style={{ padding: '20px' }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '16px',
                  borderBottom: '1px solid #f1f5f9',
                  paddingBottom: '12px',
                  flexWrap: 'wrap',
                  gap: '10px'
                }}>
                  <div>
                    <h3 style={{ margin: '0 0 4px 0', fontSize: '1.2rem', fontWeight: 800, color: '#0f172a' }}>
                      {mapItem.map_name}
                    </h3>
                    <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                      {lang === 'vi' ? 'Trạng thái kiểm định:' : 'Evaluation verdict:'} <strong style={{ color: '#1e293b' }}>{mapItem.verdict}</strong>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <div style={{
                      backgroundColor: mapItem.round3_config_c.pass ? '#dcfce7' : '#fee2e2',
                      color: mapItem.round3_config_c.pass ? '#15803d' : '#b91c1c',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px'
                    }}>
                      {mapItem.round3_config_c.pass ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                      <span>EdgeFlow RL: {mapItem.round3_config_c.pass_rate} Pass</span>
                    </div>

                    <div style={{
                      backgroundColor: '#f1f5f9',
                      color: '#475569',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      fontWeight: 600
                    }}>
                      Phase DQN: {mapItem.phase_dqn_baseline.pass_rate} Pass
                    </div>
                  </div>
                </div>

                {/* Score Summary Grid */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                  gap: '12px',
                  marginBottom: '18px'
                }}>
                  <div style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>Fixed-Time</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#334155' }}>{mapItem.fixed_time.score} s</div>
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>± {mapItem.fixed_time.ci}s</div>
                  </div>

                  <div style={{ backgroundColor: '#f8fafc', padding: '10px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600 }}>Actuated</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#334155' }}>{mapItem.actuated.score} s</div>
                    <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>± {mapItem.actuated.ci}s</div>
                  </div>

                  <div style={{ backgroundColor: '#f0f9ff', padding: '10px', borderRadius: '8px', border: '1px solid #bae6fd' }}>
                    <div style={{ fontSize: '0.7rem', color: '#0369a1', fontWeight: 600 }}>Max-Pressure+MR</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0284c7' }}>{mapItem.max_pressure_mr.score} s</div>
                    <div style={{ fontSize: '0.7rem', color: '#0284c7' }}>± {mapItem.max_pressure_mr.ci}s</div>
                  </div>

                  <div style={{ backgroundColor: '#ecfdf5', padding: '10px', borderRadius: '8px', border: '1px solid #a7f3d0' }}>
                    <div style={{ fontSize: '0.7rem', color: '#065f46', fontWeight: 600 }}>FlowTheory+MR</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#059669' }}>{mapItem.flow_theory_mr.score} s</div>
                    <div style={{ fontSize: '0.7rem', color: '#059669' }}>± {mapItem.flow_theory_mr.ci}s</div>
                  </div>

                  <div style={{ backgroundColor: '#fffbeb', padding: '10px', borderRadius: '8px', border: '1px solid #fde68a' }}>
                    <div style={{ fontSize: '0.7rem', color: '#92400e', fontWeight: 600 }}>Phase DQN Baseline</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#d97706' }}>{mapItem.phase_dqn_baseline.score} s</div>
                    <div style={{ fontSize: '0.7rem', color: '#d97706' }}>± {mapItem.phase_dqn_baseline.ci}s</div>
                  </div>

                  <div style={{ backgroundColor: '#f5f3ff', padding: '10px', borderRadius: '8px', border: '2px solid #8b5cf6' }}>
                    <div style={{ fontSize: '0.7rem', color: '#6d28d9', fontWeight: 700 }}>EdgeFlow RL</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#7c3aed' }}>{mapItem.round3_config_c.score} s</div>
                    <div style={{ fontSize: '0.7rem', color: '#7c3aed' }}>± {mapItem.round3_config_c.ci}s</div>
                  </div>
                </div>

                {/* Case Breakdown Table */}
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left', color: '#475569' }}>
                        <th style={{ padding: '8px 12px' }}>{lang === 'vi' ? 'Kịch bản tải' : 'Workload Case'}</th>
                        <th style={{ padding: '8px 12px' }}>Fixed-Time (s)</th>
                        <th style={{ padding: '8px 12px' }}>Best Deterministic (s)</th>
                        <th style={{ padding: '8px 12px' }}>Phase DQN Baseline (s)</th>
                        <th style={{ padding: '8px 12px', color: '#7c3aed' }}>EdgeFlow RL (s)</th>
                        <th style={{ padding: '8px 12px' }}>{lang === 'vi' ? 'Độ lợi EdgeFlow RL' : 'EdgeFlow RL Gain vs Det'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(mapItem.cases).map(([caseKey, caseVals]) => {
                        const diff = (caseVals.config_c - caseVals.best_det).toFixed(1);
                        const isWin = Number(diff) <= 0;
                        return (
                          <tr key={caseKey} style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '8px 12px', fontWeight: 600, textTransform: 'capitalize' }}>
                              {caseKey.replace(/_/g, ' ')}
                            </td>
                            <td style={{ padding: '8px 12px', color: '#64748b' }}>{caseVals.fixed_time.toFixed(1)}</td>
                            <td style={{ padding: '8px 12px', fontWeight: 600, color: '#0369a1' }}>{caseVals.best_det.toFixed(1)}</td>
                            <td style={{ padding: '8px 12px', color: '#d97706' }}>{caseVals.baseline_dqn.toFixed(1)}</td>
                            <td style={{ padding: '8px 12px', fontWeight: 700, color: '#7c3aed' }}>{caseVals.config_c.toFixed(1)}</td>
                            <td style={{ padding: '8px 12px' }}>
                              <span style={{
                                color: isWin ? '#16a34a' : '#ea580c',
                                fontWeight: 700
                              }}>
                                {isWin ? `${diff} s` : `+${diff} s`}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT 3: RESEARCH QUALIFICATION GATE */}
      {activeMainTab === 'qualification' && (
        <div className="card">
          <div style={{ marginBottom: '18px' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: '0 0 6px 0', color: '#1e293b' }}>
              {lang === 'vi' ? 'Tiêu Chí & Kết Quả Cổng Thẩm Định Nghiên Cứu (Qualification Gate)' : 'Research Qualification Gate & Paired Promotion Criteria'}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b', margin: 0, lineHeight: 1.5 }}>
              {lang === 'vi'
                ? 'Để được thăng cấp (Promoted) vào codebase chính thức, mô hình học máy bắt buộc phải thỏa mãn: Không có hồi quy độ trễ > 5%, tỉ lệ hoàn thành > 98%, không hồi quy đuôi đợi (p95 và worst-approach wait), đồng thời cải thiện ≥ 5% so với Max-Pressure và EdgeFlow với khoảng tin cậy bootstrap 95% dương.'
                : 'To be officially promoted into the mainline codebase, a learned policy must satisfy: ≤5% delay regression, ≥98% vehicle completion, no tail regressions (p95 & worst approach), and ≥5% overall delay improvement over Max-Pressure & EdgeFlow with positive bootstrap 95% CIs.'}
            </p>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #e2e8f0', textAlign: 'left', color: '#334155' }}>
                  <th style={{ padding: '10px 14px' }}>{t.colMap}</th>
                  <th style={{ padding: '10px 14px' }}>Chính Sách Đánh Giá</th>
                  <th style={{ padding: '10px 14px' }}>vs Fixed-Time</th>
                  <th style={{ padding: '10px 14px' }}>vs Actuated</th>
                  <th style={{ padding: '10px 14px' }}>vs Max-Pressure</th>
                  <th style={{ padding: '10px 14px' }}>vs EdgeFlow</th>
                  <th style={{ padding: '10px 14px', textAlign: 'center' }}>Trạng Thái Cổng</th>
                  <th style={{ padding: '10px 14px' }}>Lý Do Cụ Thể</th>
                </tr>
              </thead>
              <tbody>
                {rlData.qualification_gate.map((item, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 700, color: '#0f172a' }}>{item.map}</td>
                    <td style={{ padding: '10px 14px', color: '#64748b', fontSize: '0.8rem' }}>{item.policy}</td>
                    <td style={{ padding: '10px 14px', color: '#16a34a', fontWeight: 600 }}>{item.vs_fixed_time}</td>
                    <td style={{ padding: '10px 14px', color: item.vs_actuated.startsWith('+') ? '#16a34a' : '#dc2626' }}>{item.vs_actuated}</td>
                    <td style={{ padding: '10px 14px', color: item.vs_max_pressure.startsWith('+') ? '#16a34a' : '#dc2626', fontWeight: 600 }}>{item.vs_max_pressure}</td>
                    <td style={{ padding: '10px 14px', color: item.vs_edgeflow.startsWith('+') ? '#16a34a' : '#dc2626' }}>{item.vs_edgeflow}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                      {item.promoted ? (
                        <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={12} /> {t.promotedBadge}
                        </span>
                      ) : (
                        <span className="badge badge-slate" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <XCircle size={12} /> {t.blockedBadge}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: '0.8rem', color: '#475569' }}>
                      {item.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB CONTENT 4: ARCHITECTURE & TAKEAWAYS */}
      {activeMainTab === 'architecture' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Engineering Takeaways Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '16px'
          }}>
            {rlData.engineering_takeaways.map((item, idx) => (
              <div key={idx} className="card" style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                  <Sparkles size={18} style={{ color: '#8b5cf6' }} />
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#1e293b' }}>
                    {item.title}
                  </h4>
                </div>
                <p style={{ margin: 0, fontSize: '0.85rem', color: '#475569', lineHeight: 1.5, flex: 1 }}>
                  {item.detail}
                </p>
              </div>
            ))}
          </div>

          {/* Deep dive on EdgeFlow RL Residual Algorithm */}
          <div className="card" style={{ backgroundColor: '#faf5ff', border: '1px solid #e9d5ff' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#581c87', margin: '0 0 10px 0' }}>
              {lang === 'vi' ? 'Cơ Chế Điều Khiển Học Tăng Cường Hai Tầng (Two-Tier Residual DQN)' : 'EdgeFlow RL: Two-Tier Residual Deep Q-Network Mechanics'}
            </h3>
            <div style={{ fontSize: '0.85rem', color: '#6b21a8', lineHeight: 1.6 }}>
              <p style={{ margin: '0 0 8px 0' }}>
                Khác biệt lớn nhất của <strong>EdgeFlow RL</strong> so với các mô hình RL thông thường là không để mạng nơ-ron quyết định hoàn toàn tự do (free action space). Thay vào đó, bộ điều khiển vận hành theo cơ chế phân tầng an toàn:
              </p>
              <ul style={{ margin: '0 0 12px 20px', padding: 0 }}>
                <li><strong>Cơ sở mặc định (Base Controller):</strong> Sử dụng quyết định pha tín hiệu từ <em>FlowTheory CTM</em> (mô hình truyền ô vĩ mô) và <em>Max-Pressure</em>.</li>
                <li><strong>Ngưỡng can thiệp 1 (Alt-Margin 5%):</strong> DQN chỉ chuyển sang pha của Max-Pressure khi giá trị Q-value dự đoán vượt trên 5%.</li>
                <li><strong>Ngưỡng can thiệp 2 (MP-Margin 20%):</strong> DQN chỉ chọn một pha khác hoàn toàn khi Q-value của pha đó vượt trên 20% so với quyết định tất định.</li>
                <li><strong>Lưới an toàn Max-Red 40s:</strong> Khi xe tại bất kỳ nhánh nào đợi quá 40 giây, không gian hành động lập tức bị giới hạn chỉ cho phép các pha giải tỏa nhánh đó, loại bỏ triệt để hiện tượng xe bị bỏ rơi (starvation).</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RlBenchmarkReport;
