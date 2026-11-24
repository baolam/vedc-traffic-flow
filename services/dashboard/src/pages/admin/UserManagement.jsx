import React, { useState } from 'react';
import { Info, Plus, Trash2, Users, Shield } from 'lucide-react';
import { useLanguage } from '../../hooks/useLanguage';

const ROLES = ['Admin', 'Operator', 'Viewer'];

const SEED_USERS = [
  { id: 1, name: 'Lam', email: 'lam@edgeflow.local', role: 'Admin' },
  { id: 2, name: 'Vision Operator', email: 'vision.ops@edgeflow.local', role: 'Operator' },
  { id: 3, name: 'Read-Only Viewer', email: 'viewer@edgeflow.local', role: 'Viewer' }
];

const COPY = {
  en: {
    title: 'Role-Based Access Control (RBAC)',
    subtitle: 'Manage administrative privileges, traffic operator controls, and monitoring accounts.',
    mockNotice: 'Role authorization model for multi-tenant traffic centers. Account sessions and API JWT token validation are scoped per role.',
    columns: {
      name: 'Full Name',
      email: 'Corporate Email',
      role: 'Assigned Role',
      actions: 'Action'
    },
    roles: {
      Admin: 'Full Control & Config',
      Operator: 'Manual Phase Override',
      Viewer: 'Read-Only Telemetry'
    },
    addTitle: 'Provision New System User',
    addBtn: 'Add User Account',
    nameLabel: 'Full Name',
    emailLabel: 'Email Address',
    roleLabel: 'Select Role'
  },
  vi: {
    title: 'Phân Quyền Truy Cập Hệ Thống (RBAC)',
    subtitle: 'Quản lý đặc quyền quản trị viên, người điều phối giao thông và tài khoản chỉ xem.',
    mockNotice: 'Mô hình phân quyền đa người dùng cho trung tâm điều hành giao thông. Xác thực token phiên làm việc áp dụng theo từng vai trò.',
    columns: {
      name: 'Họ Và Tên',
      email: 'Email Công Vụ',
      role: 'Vai Trò Phân Quyền',
      actions: 'Thao Tác'
    },
    roles: {
      Admin: 'Toàn quyền cấu hình & ghi',
      Operator: 'Đè lệnh chuyển pha thủ công',
      Viewer: 'Chỉ xem telemetry'
    },
    addTitle: 'Thêm Tài Khoản Người Dùng Mới',
    addBtn: 'Tạo Tài Khoản',
    nameLabel: 'Họ Và Tên',
    emailLabel: 'Địa Chỉ Email',
    roleLabel: 'Chọn Vai Trò'
  }
};

const UserManagement = () => {
  const [lang] = useLanguage();
  const t = COPY[lang] || COPY.en;

  const [users, setUsers] = useState(SEED_USERS);
  const [draft, setDraft] = useState({ name: '', email: '', role: 'Viewer' });

  const addUser = () => {
    if (!draft.name.trim() || !draft.email.trim()) return;
    setUsers((prev) => [...prev, { id: Date.now(), ...draft }]);
    setDraft({ name: '', email: '', role: 'Viewer' });
  };

  const removeUser = (id) => setUsers((prev) => prev.filter((u) => u.id !== id));

  const setRole = (id, role) => setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, role } : u)));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{
        display: 'flex', gap: '10px', alignItems: 'flex-start', backgroundColor: '#f0f9ff',
        border: '1px solid #bae6fd', borderRadius: '8px', padding: '12px 16px', fontSize: '0.8rem', color: '#0369a1'
      }}>
        <Info size={17} style={{ flexShrink: 0, marginTop: '1px' }} />
        <span>{t.mockNotice}</span>
      </div>

      {/* Users Table Card */}
      <div className="card" style={{ padding: 0, overflow: 'hidden', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ textAlign: 'left', backgroundColor: '#f8fafc', color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
              <th style={{ padding: '10px 16px', fontWeight: 700 }}>{t.columns.name}</th>
              <th style={{ padding: '10px 16px', fontWeight: 700 }}>{t.columns.email}</th>
              <th style={{ padding: '10px 16px', fontWeight: 700 }}>{t.columns.role}</th>
              <th style={{ padding: '10px 16px', fontWeight: 700, textAlign: 'right' }}>{t.columns.actions}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '10px 16px', fontWeight: 700, color: '#0f172a' }}>{u.name}</td>
                <td style={{ padding: '10px 16px', color: '#64748b', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>{u.email}</td>
                <td style={{ padding: '10px 16px' }}>
                  <select
                    value={u.role}
                    onChange={(e) => setRole(u.id, e.target.value)}
                    style={{ 
                      border: '1px solid #cbd5e1', borderRadius: '6px', 
                      padding: '5px 10px', fontSize: '0.8rem', fontWeight: 700,
                      color: u.role === 'Admin' ? '#dc2626' : u.role === 'Operator' ? '#0284c7' : '#16a34a',
                      backgroundColor: '#ffffff', outline: 'none' 
                    }}
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r} ({t.roles[r]})</option>)}
                  </select>
                </td>
                <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                  <button
                    onClick={() => removeUser(u.id)}
                    title="Remove User"
                    style={{ 
                      border: 'none', background: 'none', color: '#dc2626', 
                      cursor: 'pointer', display: 'inline-flex', padding: '4px' 
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add User Form Card */}
      <div className="card" style={{ padding: '20px', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
        <h3 style={{ fontSize: '0.96rem', margin: '0 0 14px 0', fontWeight: 800, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Users size={18} color="#0284c7" /> {t.addTitle}
        </h3>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: '0.76rem', color: '#475569', marginBottom: '4px', fontWeight: 700 }}>
              {t.nameLabel}
            </label>
            <input
              value={draft.name}
              onChange={(e) => setDraft((p) => ({ ...p, name: e.target.value }))}
              placeholder="e.g. Nguyen Van A"
              style={{ width: '100%', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '8px 12px', fontSize: '0.82rem', outline: 'none' }}
            />
          </div>
          <div style={{ flex: '1 1 240px' }}>
            <label style={{ display: 'block', fontSize: '0.76rem', color: '#475569', marginBottom: '4px', fontWeight: 700 }}>
              {t.emailLabel}
            </label>
            <input
              value={draft.email}
              onChange={(e) => setDraft((p) => ({ ...p, email: e.target.value }))}
              placeholder="e.g. operator@edgeflow.gov.vn"
              style={{ width: '100%', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '8px 12px', fontSize: '0.82rem', outline: 'none' }}
            />
          </div>
          <div style={{ minWidth: '160px' }}>
            <label style={{ display: 'block', fontSize: '0.76rem', color: '#475569', marginBottom: '4px', fontWeight: 700 }}>
              {t.roleLabel}
            </label>
            <select
              value={draft.role}
              onChange={(e) => setDraft((p) => ({ ...p, role: e.target.value }))}
              style={{ width: '100%', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '8px 12px', fontSize: '0.82rem', color: '#0f172a', backgroundColor: '#ffffff', outline: 'none' }}
            >
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <button 
            className="btn btn-primary" 
            onClick={addUser} 
            style={{ padding: '8px 18px', display: 'flex', alignItems: 'center', gap: '6px', height: '37px' }}
          >
            <Plus size={16} /> {t.addBtn}
          </button>
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
