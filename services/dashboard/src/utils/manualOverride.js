// Manual phase override as the ESP32 really handled it. The API derives `manual_override` from the device ACKs
// (GET /api/v1/network/state/{node}); graph-control keeps re-sending the phase until the safety rules allow it.

export const OVERRIDE_IN_PROGRESS = ['SENT', 'WAITING', 'CLEARING'];

const TONES = {
  info: { background: '#eff6ff', border: '#3b82f6', color: '#1d4ed8' },
  warn: { background: '#fffbeb', border: '#f59e0b', color: '#b45309' },
  ok: { background: '#f0fdf4', border: '#16a34a', color: '#15803d' },
  error: { background: '#fef2f2', border: '#ef4444', color: '#dc2626' },
  neutral: { background: '#f8fafc', border: '#cbd5e1', color: '#475569' }
};

/** { tone, colors, title, detail } for an override view from the API, or null when there is nothing to show. */
export function describeOverride(override) {
  if (!override) return null;
  const target = override.target_phase_id;
  const reason = override.last_reason ? `ESP32: "${override.last_reason}". ` : '';
  const views = {
    SENT: ['info', `Đã gửi lệnh ${target}`, 'Đang chờ ESP32 trả lời…'],
    WAITING: ['warn', `ESP32 chưa đổi sang ${target}`,
      `${reason}Graph-control gửi lại mỗi giây cho tới khi luật an toàn (xanh tối thiểu 5 s, không cắt ngang vàng/đỏ) cho phép.`],
    CLEARING: ['warn', `Đang chuyển sang ${target}`, 'ESP32 đã nhận lệnh: vàng 3 s → đỏ toàn bộ 2 s → xanh.'],
    APPLIED: ['ok', `${target} đang xanh theo lệnh tay`,
      `Giữ ưu tiên thêm ${override.hold_remaining_s ?? '?'} s, sau đó thuật toán điều khiển lại.`],
    ENDED: ['neutral', `Đã hết ưu tiên ${target}`, 'Thuật toán đã điều khiển lại nút này.'],
    NOT_APPLIED: ['error', `Không đổi được sang ${target}`,
      `${reason || 'ESP32 không trả lời (mất kết nối, safe-stop, hoặc graph-control không chạy). '}Lệnh đã bị bỏ.`]
  };
  const view = views[override.status];
  if (!view) return null;
  const [tone, title, detail] = view;
  return { tone, colors: TONES[tone], title, detail };
}

/** Error text for a failed POST /api/v1/control/override (the command never reached the ESP32). */
export function overrideRequestError(detail) {
  return {
    tone: 'error',
    colors: TONES.error,
    title: 'Lệnh chưa được gửi',
    detail: detail || 'Không gọi được API.'
  };
}
