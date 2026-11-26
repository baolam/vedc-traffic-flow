import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Radio, Wifi, Filter, Search, Pause, Play, ChevronDown, ChevronUp, 
  Copy, Check, RefreshCw, Terminal, AlertTriangle, CheckCircle2, ArrowRight
} from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

const KIND_COLORS = {
  telemetry: { bg: '#e0f2fe', text: '#0369a1', border: '#bae6fd', label: 'TELEMETRY' },
  health: { bg: '#dcfce7', text: '#15803d', border: '#bbf7d0', label: 'HEALTH' },
  command: { bg: '#f3e8ff', text: '#7e22ce', border: '#e9d5ff', label: 'COMMAND' },
  ack: { bg: '#ccfbf1', text: '#0f766e', border: '#99f6e4', label: 'ACK' },
  fault: { bg: '#fee2e2', text: '#b91c1c', border: '#fecaca', label: 'FAULT' },
  other: { bg: '#f1f5f9', text: '#475569', border: '#e2e8f0', label: 'MQTT' }
};

const COPY = {
  en: {
    title: 'Realtime MQTT Packet Stream',
    subtitle: 'Direct wire inspection of packets on edgeflow/v1/# topics',
    brokerConnected: 'Broker Connected',
    brokerDisconnected: 'Broker Standby',
    packetsCount: (count) => `${count} packets captured`,
    filterAll: 'ALL',
    searchPlaceholder: 'Search topic, node or payload...',
    pause: 'Pause',
    resume: 'Resume',
    copyJson: 'Copy JSON',
    copied: 'Copied!',
    noPackets: 'No MQTT packets match this filter yet. Listening on edgeflow/v1/# ...',
    expandPayload: 'Payload Details',
    collapsePayload: 'Hide',
    receivedAgo: (s) => `${s}s ago`,
    justNow: 'just now'
  },
  vi: {
    title: 'Dòng Gói Tin Trạng Thái MQTT Thời Gian Thực',
    subtitle: 'Giám sát trực tiếp gói tin trên các kênh edgeflow/v1/#',
    brokerConnected: 'Broker Đã Kết Nối',
    brokerDisconnected: 'Broker Đang Chờ',
    packetsCount: (count) => `${count} gói tin đã ghi nhận`,
    filterAll: 'TẤT CẢ',
    searchPlaceholder: 'Tìm theo topic, node hoặc dữ liệu...',
    pause: 'Tạm dừng',
    resume: 'Tiếp tục',
    copyJson: 'Sao chép JSON',
    copied: 'Đã sao chép!',
    noPackets: 'Chưa có gói tin MQTT nào khớp bộ lọc. Đang lắng nghe kênh edgeflow/v1/# ...',
    expandPayload: 'Chi tiết gói tin',
    collapsePayload: 'Thu gọn',
    receivedAgo: (s) => `${s}s trước`,
    justNow: 'vừa xong'
  }
};

const MqttPacketInspector = ({
  nodeId = null,
  compact = false,
  maxHeight = '360px',
  pollIntervalMs = 1500,
  showHeader = true
}) => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;
  const isVi = lang === 'vi';

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const [packets, setPackets] = useState([]);
  const [brokerInfo, setBrokerInfo] = useState({
    connected: false,
    broker: 'localhost:1883',
    total_packets: 0,
    last_received_ms: null
  });
  const [filterKind, setFilterKind] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const fetchPackets = useCallback(() => {
    if (isPaused) return;

    let url = `${apiBase}/api/v1/mqtt/packets?limit=80`;
    if (filterKind !== 'ALL') {
      url += `&kind=${filterKind.toLowerCase()}`;
    }
    if (nodeId) {
      url += `&node_id=${encodeURIComponent(nodeId)}`;
    }

    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.packets)) {
          setPackets(data.packets);
          setBrokerInfo({
            connected: Boolean(data.connected),
            broker: data.broker || 'localhost:1883',
            total_packets: data.total_packets || data.packets.length,
            last_received_ms: data.last_received_ms
          });
        }
      })
      .catch(() => {});
  }, [apiBase, filterKind, nodeId, isPaused]);

  useEffect(() => {
    fetchPackets();
    const interval = setInterval(fetchPackets, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchPackets, pollIntervalMs]);

  // Client-side search filtering
  const filteredPackets = useMemo(() => {
    if (!searchQuery.trim()) return packets;
    const q = searchQuery.toLowerCase();
    return packets.filter(p => {
      const topicMatch = (p.topic || '').toLowerCase().includes(q);
      const nodeMatch = (p.node_id || '').toLowerCase().includes(q);
      const summaryMatch = (p.summary || '').toLowerCase().includes(q);
      const payloadMatch = p.payload ? JSON.stringify(p.payload).toLowerCase().includes(q) : false;
      return topicMatch || nodeMatch || summaryMatch || payloadMatch;
    });
  }, [packets, searchQuery]);

  const handleCopy = (id, payload) => {
    try {
      navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (e) {
      console.warn('Failed to copy to clipboard', e);
    }
  };

  const kinds = ['ALL', 'TELEMETRY', 'HEALTH', 'COMMAND', 'ACK', 'FAULT'];

  return (
    <div style={{
      backgroundColor: '#ffffff',
      borderRadius: compact ? '8px' : '12px',
      border: '1px solid #e2e8f0',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Header */}
      {showHeader && (
        <div style={{
          padding: compact ? '10px 14px' : '14px 18px',
          borderBottom: '1px solid #e2e8f0',
          backgroundColor: '#f8fafc',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '10px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              backgroundColor: '#e0f2fe',
              color: '#0284c7',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Radio size={18} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h4 style={{ margin: 0, fontSize: compact ? '0.88rem' : '0.98rem', fontWeight: 800, color: '#0f172a' }}>
                  {t.title}
                </h4>
                {nodeId && (
                  <span style={{
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    padding: '1px 6px',
                    borderRadius: '4px',
                    backgroundColor: '#e2e8f0',
                    color: '#334155'
                  }}>
                    Node {nodeId}
                  </span>
                )}
              </div>
              {!compact && (
                <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '2px' }}>
                  {t.subtitle}
                </div>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* Broker Status */}
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '9999px',
              backgroundColor: brokerInfo.connected ? '#dcfce7' : '#f1f5f9',
              color: brokerInfo.connected ? '#15803d' : '#64748b',
              border: `1px solid ${brokerInfo.connected ? '#86efac' : '#cbd5e1'}`
            }}>
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: brokerInfo.connected ? '#22c55e' : '#94a3b8'
              }} />
              {brokerInfo.connected ? `${t.brokerConnected} (${brokerInfo.broker})` : `${t.brokerDisconnected} (${brokerInfo.broker})`}
            </span>

            {/* Total Packets count */}
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '6px',
              backgroundColor: '#f1f5f9',
              color: '#475569'
            }}>
              {t.packetsCount(filteredPackets.length)}
            </span>

            {/* Pause / Resume Button */}
            <button
              onClick={() => setIsPaused(!isPaused)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                border: '1px solid #cbd5e1',
                borderRadius: '6px',
                padding: '3px 8px',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                backgroundColor: isPaused ? '#fef9c3' : '#ffffff',
                color: isPaused ? '#a16207' : '#475569'
              }}
            >
              {isPaused ? <Play size={12} /> : <Pause size={12} />}
              {isPaused ? t.resume : t.pause}
            </button>
          </div>
        </div>
      )}

      {/* Toolbar: Filters & Search */}
      <div style={{
        padding: '8px 14px',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #f1f5f9',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '8px'
      }}>
        {/* Kind Filters */}
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {kinds.map(k => {
            const active = filterKind === k;
            return (
              <button
                key={k}
                onClick={() => setFilterKind(k)}
                style={{
                  border: 'none',
                  padding: '3px 8px',
                  borderRadius: '5px',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: active ? '#0284c7' : '#f1f5f9',
                  color: active ? '#ffffff' : '#64748b',
                  transition: 'all 0.15s ease'
                }}
              >
                {k === 'ALL' ? t.filterAll : k}
              </button>
            );
          })}
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={13} color="#94a3b8" style={{ position: 'absolute', left: '8px' }} />
          <input
            type="text"
            placeholder={t.searchPlaceholder}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              padding: '3px 8px 3px 26px',
              fontSize: '0.72rem',
              border: '1px solid #cbd5e1',
              borderRadius: '5px',
              outline: 'none',
              width: '180px'
            }}
          />
        </div>
      </div>

      {/* Packet Stream List (Dark Console Look) */}
      <div style={{
        backgroundColor: '#090d16',
        padding: '10px 14px',
        maxHeight: maxHeight,
        overflowY: 'auto',
        fontFamily: 'JetBrains Mono, monospace',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        {filteredPackets.length === 0 ? (
          <div style={{
            color: '#64748b',
            fontSize: '0.76rem',
            padding: '24px 10px',
            textAlign: 'center'
          }}>
            {t.noPackets}
          </div>
        ) : (
          filteredPackets.map(pkt => {
            const kindKey = (pkt.kind || 'other').toLowerCase();
            const colorConf = KIND_COLORS[kindKey] || KIND_COLORS.other;
            const isExpanded = expandedId === pkt.id;
            const isCopied = copiedId === pkt.id;

            return (
              <div
                key={pkt.id}
                style={{
                  backgroundColor: isExpanded ? '#0f172a' : '#090d16',
                  border: `1px solid ${isExpanded ? '#334155' : '#1e293b'}`,
                  borderRadius: '6px',
                  padding: '7px 10px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  transition: 'background-color 0.15s ease'
                }}
              >
                {/* Single Packet Header Row */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  fontSize: '0.73rem',
                  flexWrap: 'wrap'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    {/* Time */}
                    <span style={{ color: '#94a3b8' }}>
                      [{pkt.timestamp || '00:00:00'}]
                    </span>

                    {/* Kind Pill */}
                    <span style={{
                      padding: '1px 5px',
                      borderRadius: '3px',
                      fontSize: '0.65rem',
                      fontWeight: 800,
                      backgroundColor: colorConf.bg,
                      color: colorConf.text,
                      border: `1px solid ${colorConf.border}`
                    }}>
                      {colorConf.label}
                    </span>

                    {/* Topic */}
                    <span style={{ color: '#38bdf8', fontWeight: 700 }}>
                      {pkt.topic}
                    </span>

                    {/* Node Tag */}
                    {pkt.node_id && (
                      <span style={{
                        color: '#facc15',
                        backgroundColor: 'rgba(250, 204, 21, 0.1)',
                        padding: '1px 5px',
                        borderRadius: '3px',
                        fontSize: '0.67rem'
                      }}>
                        {pkt.node_id}
                      </span>
                    )}
                  </div>

                  {/* Expand / Inspect Action */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : pkt.id)}
                      style={{
                        background: 'transparent',
                        border: '1px solid #334155',
                        borderRadius: '4px',
                        padding: '2px 6px',
                        color: isExpanded ? '#38bdf8' : '#94a3b8',
                        fontSize: '0.67rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      {isExpanded ? t.collapsePayload : t.expandPayload}
                      {isExpanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </button>
                  </div>
                </div>

                {/* Summary Row */}
                <div style={{
                  color: pkt.level === 'CRITICAL' ? '#f87171' : pkt.level === 'WARNING' ? '#fbbf24' : '#e2e8f0',
                  fontSize: '0.74rem',
                  lineHeight: '1.3'
                }}>
                  {pkt.summary || JSON.stringify(pkt.payload || {})}
                </div>

                {/* Collapsible Full JSON Payload */}
                {isExpanded && pkt.payload && (
                  <div style={{
                    marginTop: '4px',
                    padding: '8px',
                    borderRadius: '5px',
                    backgroundColor: '#020617',
                    border: '1px solid #1e293b',
                    position: 'relative'
                  }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '6px',
                      paddingBottom: '4px',
                      borderBottom: '1px solid #1e293b'
                    }}>
                      <span style={{ fontSize: '0.68rem', color: '#64748b' }}>
                        JSON Payload (QoS 0 · Clean Session)
                      </span>
                      <button
                        onClick={() => handleCopy(pkt.id, pkt.payload)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: isCopied ? '#4ade80' : '#38bdf8',
                          fontSize: '0.68rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px'
                        }}
                      >
                        {isCopied ? <Check size={11} /> : <Copy size={11} />}
                        {isCopied ? t.copied : t.copyJson}
                      </button>
                    </div>
                    <pre style={{
                      margin: 0,
                      color: '#a5f3fc',
                      fontSize: '0.7rem',
                      lineHeight: '1.35',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all'
                    }}>
                      {JSON.stringify(pkt.payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default MqttPacketInspector;
