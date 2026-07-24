// AlertModal.jsx
import React from 'react';
import './AlertModal.css';

const AlertModal = ({ alert, onClose, onResolve }) => {
    if (!alert) return null;

    // Get data from alert object
    const device = alert.device || {};
    const org = alert.organization || {};
    const additional = alert.additional_info || {};

    // If alert has no device data, use fallback
    const hostname = device.hostname || alert.hostname || 'Unknown';
    const ipAddress = device.ip_address || alert.ip_address || 'Unknown';
    
    // Get problem from alert or use default
    const problem = alert.problem || 'Device issue detected';
    const cause = alert.cause || 'Diagnostic engine analyzing...';
    const solutions = alert.solutions || [
        'Check device connectivity',
        'Verify power status',
        'Check network cable'
    ];
    const severity = alert.severity || 'HIGH';
    const status = alert.status || alert.current_status || 'OPEN';

    // Get organization name
    const orgName = org.name || alert.organization_name || '—';
    const orgType = org.type || alert.org_type || '—';
    const region = org.region || alert.region || '—';

    // Get severity icon
    const getSeverityIcon = (sev) => {
        const icons = {
            'CRITICAL': '🚨',
            'HIGH': '🔴',
            'MEDIUM': '🟡',
            'LOW': '🟢'
        };
        return icons[sev] || '⚠️';
    };

    // Get status color
    const getStatusColor = (stat) => {
        const colors = {
            'DOWN': '#ff4757',
            'WARNING': '#f39c12',
            'ONLINE': '#2ecc71',
            'OPEN': '#ff4757',
            'UNKNOWN': '#7a8aa0'
        };
        return colors[stat] || '#7a8aa0';
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="alert-modal" onClick={(e) => e.stopPropagation()}>
                
                {/* ============================================================ */}
                {/* HEADER */}
                {/* ============================================================ */}
                <div className="modal-header">
                    <div>
                        <h2>
                            {getSeverityIcon(severity)} {severity} Alert
                        </h2>
                        <p>
                            {hostname} • {ipAddress}
                        </p>
                    </div>
                    <button className="close-button" onClick={onClose}>×</button>
                </div>

                {/* ============================================================ */}
                {/* DEVICE INFO CARD */}
                {/* ============================================================ */}
                <div className="device-info-card">
                    <div className="device-info-grid">
                        <div>
                            <label>Hostname</label>
                            <strong>{hostname}</strong>
                        </div>
                        <div>
                            <label>IP Address</label>
                            <strong>{ipAddress}</strong>
                        </div>
                        <div>
                            <label>Device Type</label>
                            <strong>{device.device_type || 'Unknown'}</strong>
                        </div>
                        <div>
                            <label>Criticality</label>
                            <span className={`criticality-badge ${(device.criticality || 'MEDIUM').toLowerCase()}`}>
                                {device.criticality || 'MEDIUM'}
                            </span>
                        </div>
                        <div>
                            <label>VLAN ID</label>
                            <strong>{device.vlan_id || '—'}</strong>
                        </div>
                        <div>
                            <label>Status</label>
                            <span 
                                className="status-badge"
                                style={{ background: getStatusColor(status) }}
                            >
                                {status}
                            </span>
                        </div>
                    </div>
                </div>

                {/* ============================================================ */}
                {/* ORGANIZATION INFO */}
                {/* ============================================================ */}
                <div className="org-info">
                    <div className="org-row">
                        <span className="org-label">🏢 Organization</span>
                        <span className="org-value">{orgName}</span>
                    </div>
                    <div className="org-row">
                        <span className="org-label">📂 Type</span>
                        <span className="org-value">{orgType}</span>
                    </div>
                    <div className="org-row">
                        <span className="org-label">🌍 Region</span>
                        <span className="org-value region-tag">{region}</span>
                    </div>
                </div>

                {/* ============================================================ */}
                {/* PROBLEM DETAIL */}
                {/* ============================================================ */}
                <div className="detail-section problem">
                    <h3>📋 Problem Detail</h3>
                    <p className="problem-text">{problem}</p>
                    {(status === 'DOWN' || status === 'OPEN' || status === 'CRITICAL') && (
                        <div className="offline-badge">🚨 Device is OFFLINE / CRITICAL</div>
                    )}
                </div>

                {/* ============================================================ */}
                {/* POSSIBLE CAUSE */}
                {/* ============================================================ */}
                <div className="detail-section">
                    <h3>🔍 Possible Cause</h3>
                    <p>{cause}</p>
                </div>

                {/* ============================================================ */}
                {/* RECOMMENDED SOLUTIONS */}
                {/* ============================================================ */}
                <div className="detail-section solution">
                    <h3>✅ Recommended Solutions</h3>
                    <ul>
                        {solutions.map((solution, index) => (
                            <li key={index}>{solution}</li>
                        ))}
                    </ul>
                </div>

                {/* ============================================================ */}
                {/* ADDITIONAL INFO */}
                {/* ============================================================ */}
                <div className="additional-info">
                    <div className="additional-grid">
                        <div>
                            <label>Failure Count</label>
                            <span>{additional.failure_count ?? 0}</span>
                        </div>
                        <div>
                            <label>Parent Switch</label>
                            <span>{additional.parent_switch || '—'}</span>
                        </div>
                        <div>
                            <label>Last Check</label>
                            <span>{alert.timestamp ? new Date(alert.timestamp).toLocaleString() : '—'}</span>
                        </div>
                        <div>
                            <label>Uptime</label>
                            <span>{additional.uptime || 'Unknown'}</span>
                        </div>
                    </div>
                </div>

                {/* ============================================================ */}
                {/* ACTIONS */}
                {/* ============================================================ */}
                <div className="modal-actions">
                    <button className="close-modal-btn" onClick={onClose}>
                        Close
                    </button>
                    <button className="resolve-button" onClick={onResolve}>
                        ✅ Resolve
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AlertModal;