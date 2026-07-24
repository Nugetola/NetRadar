import { useEffect, useState, useCallback } from "react";
import "./App.css";
import DeviceManagement from './components/DeviceManagement';
import NetworkTopology from './components/NetworkTopology';
import AgentManagement from './components/AgentManagement';

const API_BASE = "http://127.0.0.1:8000/api/v1";

// ============================================================
// HELPER FUNCTIONS
// ============================================================
function formatRelativeTime(isoString) {
  if (!isoString) return "Unknown";
  const diffMs = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins === 1) return "1 min ago";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs} hr ago`;
}

function statusMeta(status) {
  switch ((status || "").toUpperCase()) {
    case "ONLINE":
    case "UP":
      return { dot: "🟢", label: "Online", cls: "online" };
    case "CRITICAL":
    case "DOWN":
      return { dot: "🔴", label: "Critical", cls: "critical" };
    case "WARNING":
    case "UNSTABLE":
      return { dot: "🟡", label: "Warning", cls: "warning" };
    default:
      return { dot: "⚪", label: "Unknown", cls: "unknown" };
  }
}

// ============================================================
// APP COMPONENT
// ============================================================
function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [devices, setDevices] = useState([]);
  const [branches, setBranches] = useState([]);
  const [agents, setAgents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [backendError, setBackendError] = useState(false);

  // ============================================================
  // DATA LOADING - REAL BACKEND ONLY
  // ============================================================
  const transformDevice = (backendDevice) => ({
    id: backendDevice.id,
    hostname: backendDevice.hostname || "Unknown",
    ip_address: backendDevice.ip_address || "0.0.0.0",
    status: backendDevice.status || "UNKNOWN",
    latency_ms: backendDevice.latency_ms || backendDevice.latency || null,
    packet_loss: backendDevice.packet_loss || 0,
    last_check: backendDevice.last_check || backendDevice.recorded_at || new Date().toISOString(),
    criticality: backendDevice.criticality || "MEDIUM",
    device_type: backendDevice.device_type || "Unknown",
    vlan_id: backendDevice.vlan_id || null,
    branch_id: backendDevice.branch_id || null,
    parent_switch_id: backendDevice.parent_switch_id || null,
  });

  const loadDevices = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/devices`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      let deviceList = data.devices || data || [];
      if (!Array.isArray(deviceList)) {
        deviceList = Object.values(deviceList);
      }
      setDevices(deviceList.map(transformDevice));
      setBackendError(false);
    } catch (error) {
      console.error("❌ Failed to load devices:", error);
      setBackendError(true);
      setDevices([]);
    }
  }, []);

  const loadBranches = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/branches`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setBranches(data.branches || []);
    } catch (error) {
      console.error("❌ Failed to load branches:", error);
      setBranches([]);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/agents`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setAgents(data.agents || []);
    } catch (error) {
      console.error("❌ Failed to load agents:", error);
      setAgents([]);
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/tickets?status=OPEN`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const ticketList = data.tickets || data || [];
      const transformedAlerts = ticketList.map(ticket => ({
        id: ticket.id,
        title: `${ticket.severity} Alert`,
        hostname: 'Unknown',
        ip_address: 'Unknown',
        severity: ticket.severity || 'MEDIUM',
        created_at: ticket.opened_at || new Date().toISOString(),
        problem: ticket.diagnostics?.details || `Device is ${ticket.status}`,
        cause: ticket.diagnostics?.root_cause_analysis || 'Diagnostic engine analyzing...',
        solution: ['Check device connectivity', 'Verify power status', 'Check network cable'],
        escalation_level: ticket.escalation_level || 1,
        status: ticket.status || 'OPEN'
      }));
      setAlerts(transformedAlerts);
    } catch (error) {
      console.error("❌ Failed to load alerts:", error);
      setAlerts([]);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([loadDevices(), loadBranches(), loadAlerts(), loadAgents()]);
    setLastUpdated(new Date());
    setLoading(false);
  }, [loadDevices, loadBranches, loadAlerts, loadAgents]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  // ============================================================
  // HANDLERS
  // ============================================================
  const handleAddDevice = (newDevice) => {
    const deviceWithId = {
      ...newDevice,
      id: `dev-${Date.now()}`
    };
    setDevices(prev => [...prev, deviceWithId]);
    showToast(`✅ Device "${newDevice.hostname}" added successfully`, 'success');
  };

  const handleEditDevice = (updatedDevice) => {
    setDevices(prev => prev.map(d => d.id === updatedDevice.id ? updatedDevice : d));
    showToast(`✅ Device "${updatedDevice.hostname}" updated successfully`, 'success');
  };

  const handleDeleteDevice = (deviceId) => {
    const device = devices.find(d => d.id === deviceId);
    setDevices(prev => prev.filter(d => d.id !== deviceId));
    showToast(`🗑️ Device "${device?.hostname}" deleted`, 'info');
  };

  const handleNodeClick = (node) => {
    console.log('Selected node:', node);
    showToast(`📍 Selected: ${node.name} (${node.ip})`, 'info');
  };

  const showToast = (message, type = 'info') => {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.transition = 'opacity 0.3s, transform 0.3s';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100px)';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  };

  // ============================================================
  // STATISTICS
  // ============================================================
  const onlineCount = devices.filter(d => d.status === 'ONLINE' || d.status === 'UP').length;
  const criticalCount = devices.filter(d => d.status === 'CRITICAL' || d.status === 'DOWN').length;
  const warningCount = devices.filter(d => d.status === 'WARNING' || d.status === 'UNSTABLE').length;
  const totalCount = devices.length || 0;
  const uptimePct = totalCount > 0 ? ((onlineCount / totalCount) * 100).toFixed(1) : 0;

  const avgLatency = totalCount > 0 ? devices.reduce((sum, d) => sum + (d.latency_ms || 0), 0) / totalCount : 0;
  const avgPacketLoss = totalCount > 0 ? devices.reduce((sum, d) => sum + (d.packet_loss || 0), 0) / totalCount : 0;
  
  const availabilityScore = totalCount > 0 ? (onlineCount / totalCount) * 40 : 0;
  const latencyScore = Math.max(0, 25 - avgLatency / 10);
  const packetLossScore = Math.max(0, 20 - avgPacketLoss * 2);
  const alertScore = Math.max(0, 15 - alerts.length * 3);
  const healthScore = Math.round(availabilityScore + latencyScore + packetLossScore + alertScore);
  const healthLabel = healthScore >= 85 ? "Healthy" : healthScore >= 60 ? "Degraded" : "Critical";
  const healthCls = healthScore >= 85 ? "healthy" : healthScore >= 60 ? "degraded" : "critical";

  // ============================================================
  // NAVIGATION
  // ============================================================
  const navItems = [
    { id: 'dashboard', icon: '📊', label: 'Dashboard' },
    { id: 'devices', icon: '🖥️', label: 'Device Management' },
    { id: 'agents', icon: '👤', label: 'Agent Management' },
    { id: 'topology', icon: '🌐', label: 'Network Topology' },
    { id: 'alerts', icon: '🔔', label: 'Alerts' },
    { id: 'reports', icon: '📈', label: 'Reports' },
    { id: 'settings', icon: '⚙️', label: 'Settings' },
  ];

  // ============================================================
  // PAGE RENDERERS
  // ============================================================
  const renderDashboard = () => (
    <>
      <section className="summary-cards">
        <div className="summary-card">
          <span className="summary-icon">🟢</span>
          <div>
            <span className="summary-value">{onlineCount}</span>
            <span className="summary-label">Online</span>
          </div>
        </div>
        <div className="summary-card critical">
          <span className="summary-icon">🔴</span>
          <div>
            <span className="summary-value">{criticalCount}</span>
            <span className="summary-label">Critical</span>
          </div>
        </div>
        <div className="summary-card warning">
          <span className="summary-icon">🟡</span>
          <div>
            <span className="summary-value">{warningCount}</span>
            <span className="summary-label">Warning</span>
          </div>
        </div>
        <div className="summary-card">
          <span className="summary-icon">📊</span>
          <div>
            <span className="summary-value">{uptimePct}%</span>
            <span className="summary-label">Uptime</span>
          </div>
        </div>
        <div className="summary-card">
          <span className="summary-icon">📦</span>
          <div>
            <span className="summary-value">{totalCount}</span>
            <span className="summary-label">Total Devices</span>
          </div>
        </div>
      </section>

      <section className="overview-grid">
        <div className="panel health-panel">
          <h2>Network Health</h2>
          <div className={`health-score ${healthCls}`}>
            <span className="score-value">{healthScore}</span>
            <span className="score-label">{healthLabel}</span>
          </div>
          <div className="health-metrics">
            <div>
              <span className="metric-label">Avg Latency</span>
              <span className="metric-value">{Math.round(avgLatency)}ms</span>
            </div>
            <div>
              <span className="metric-label">Packet Loss</span>
              <span className="metric-value">{avgPacketLoss.toFixed(1)}%</span>
            </div>
            <div>
              <span className="metric-label">Alerts</span>
              <span className="metric-value">{alerts.length}</span>
            </div>
          </div>
        </div>

        <div className="panel alerts-panel">
          <div className="panel-title">
            <div>
              <h2>🔔 Active Alerts</h2>
              <p>Click an alert to view details</p>
            </div>
            <span className="alert-count">{alerts.length}</span>
          </div>
          {alerts.length === 0 ? (
            <div className="no-alerts">✅ No active alerts</div>
          ) : (
            <div className="alerts-list">
              {alerts.slice(0, 4).map(alert => (
                <button 
                  key={alert.id} 
                  className={`alert-item ${alert.severity?.toLowerCase()}`}
                  onClick={() => setSelectedAlert(alert)}
                >
                  <div className="alert-icon">
                    {alert.severity === 'CRITICAL' ? '🔴' : alert.severity === 'WARNING' ? '🟡' : '🟠'}
                  </div>
                  <div className="alert-content">
                    <strong>{alert.title}</strong>
                    <span>{alert.hostname}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="panel devices-panel">
        <div className="panel-title">
          <div>
            <h2>Device Inventory</h2>
            <p>All monitored devices</p>
          </div>
        </div>
        <div className="table-wrap">
          <table className="devices-table">
            <thead>
              <tr>
                <th>Device</th>
                <th>IP</th>
                <th>Status</th>
                <th>Criticality</th>
                <th>VLAN</th>
                <th>Branch</th>
              </tr>
            </thead>
            <tbody>
              {devices.slice(0, 10).map(device => {
                const meta = statusMeta(device.status);
                return (
                  <tr key={device.id}>
                    <td>{device.hostname}</td>
                    <td className="mono">{device.ip_address}</td>
                    <td>
                      <span className={`status-pill ${meta.cls}`}>
                        {meta.dot} {meta.label}
                      </span>
                    </td>
                    <td>
                      <span className={`criticality-tag ${device.criticality?.toLowerCase() || 'medium'}`}>
                        {device.criticality || 'MEDIUM'}
                      </span>
                    </td>
                    <td>{device.vlan_id || '—'}</td>
                    <td>{branches.find(b => b.id === device.branch_id)?.name || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel topology-panel">
        <NetworkTopology devices={devices} branches={branches} onNodeClick={handleNodeClick} />
      </section>
    </>
  );

  const renderAlertsPage = () => (
    <div className="page-content">
      <h2 className="page-title">🔔 All Alerts</h2>
      <div className="alerts-full-list">
        {alerts.map(alert => (
          <div key={alert.id} className={`alert-full-item ${alert.severity?.toLowerCase()}`}>
            <div className="alert-full-header">
              <span className="alert-full-severity">{alert.severity}</span>
              <span className="alert-full-time">{new Date(alert.created_at).toLocaleString()}</span>
            </div>
            <h3>{alert.title}</h3>
            <p><strong>Device:</strong> {alert.hostname} ({alert.ip_address})</p>
            <p><strong>Problem:</strong> {alert.problem}</p>
            <p><strong>Cause:</strong> {alert.cause}</p>
            {alert.solution && (
              <div className="alert-full-solution">
                <strong>Solution:</strong>
                <ul>
                  {alert.solution.map((step, i) => <li key={i}>{step}</li>)}
                </ul>
              </div>
            )}
          </div>
        ))}
        {alerts.length === 0 && <div className="no-alerts">✅ No alerts</div>}
      </div>
    </div>
  );

  const renderReportsPage = () => (
    <div className="page-content">
      <h2 className="page-title">📈 Reports</h2>
      <div className="reports-grid">
        <div className="report-card">
          <h3>Uptime</h3>
          <div className="report-value">{uptimePct}%</div>
          <p>Overall uptime</p>
        </div>
        <div className="report-card">
          <h3>Health Score</h3>
          <div className="report-value">{healthScore}</div>
          <p>{healthLabel}</p>
        </div>
        <div className="report-card">
          <h3>Total Devices</h3>
          <div className="report-value">{totalCount}</div>
          <p>Monitored devices</p>
        </div>
        <div className="report-card">
          <h3>Open Alerts</h3>
          <div className="report-value">{alerts.length}</div>
          <p>Active alerts</p>
        </div>
        <div className="report-card">
          <h3>Avg Latency</h3>
          <div className="report-value">{Math.round(avgLatency)}ms</div>
          <p>Average response time</p>
        </div>
        <div className="report-card">
          <h3>Packet Loss</h3>
          <div className="report-value">{avgPacketLoss.toFixed(1)}%</div>
          <p>Average packet loss</p>
        </div>
      </div>
    </div>
  );

  const renderSettingsPage = () => (
    <div className="page-content">
      <h2 className="page-title">⚙️ Settings</h2>
      <div className="settings-grid">
        <div className="setting-group">
          <h3>General</h3>
          <div className="setting-item">
            <label>Polling Interval</label>
            <select>
              <option>30 seconds</option>
              <option>60 seconds</option>
              <option>120 seconds</option>
            </select>
          </div>
          <div className="setting-item">
            <label>Alert Debounce</label>
            <select>
              <option>1 minute</option>
              <option>3 minutes</option>
              <option>5 minutes</option>
            </select>
          </div>
          <div className="setting-item">
            <label>Data Retention</label>
            <select>
              <option>30 days</option>
              <option>60 days</option>
              <option>90 days</option>
            </select>
          </div>
        </div>
        <div className="setting-group">
          <h3>Notifications</h3>
          <div className="setting-item">
            <label>SMS Gateway URL</label>
            <input type="text" placeholder="https://sms-provider.com/api/send" />
          </div>
          <div className="setting-item">
            <label>SMS API Key</label>
            <input type="password" placeholder="••••••••••••••••" />
          </div>
          <div className="setting-item">
            <label>SMTP Server</label>
            <input type="text" placeholder="smtp.gmail.com" />
          </div>
          <div className="setting-item">
            <label>Alert Email</label>
            <input type="email" placeholder="alerts@oic.com.et" />
          </div>
        </div>
      </div>
    </div>
  );

  // ============================================================
  // MAIN RENDER
  // ============================================================
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <button 
            className="sidebar-toggle" 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          >
            ☰
          </button>
          
         <div className="brand">
  <svg 
    viewBox="0 0 100 100" 
    width="36" 
    height="36" 
    style={{ filter: 'drop-shadow(0 0 4px #00b4d8)' }}
  >
    <circle cx="50" cy="50" r="45" fill="none" stroke="#00b4d8" strokeWidth="1.5" opacity="0.35"/>
    <circle cx="50" cy="50" r="30" fill="none" stroke="#00b4d8" strokeWidth="1.5" opacity="0.35"/>
    <circle cx="50" cy="50" r="15" fill="none" stroke="#00b4d8" strokeWidth="1.5" opacity="0.35"/>
    <line x1="50" y1="50" x2="50" y2="8" stroke="#00b4d8" strokeWidth="2.5" 
      style={{ transformOrigin: '50px 50px', animation: 'radarRotate 3s linear infinite' }}/>
    <circle cx="50" cy="50" r="3" fill="#00b4d8"/>
  </svg>
  <div>
    <small>OIC NETWORK OPERATIONS</small>
    <h1>NetRadar</h1>
  </div>
</div>
</div>
        <div className="topbar-right">
          <span className={`monitoring-status ${backendError ? 'mock' : ''}`}>
            <span className={`pulse-dot ${backendError ? 'mock' : ''}`} /> 
            {backendError ? '⚠️ Backend Offline' : 'Live'}
          </span>
          <span className="last-updated">
            {lastUpdated ? `Updated ${formatRelativeTime(lastUpdated.toISOString())}` : '—'}
          </span>
          <button className="icon-button" onClick={refreshAll} disabled={loading}>
            {loading ? '⟳' : '🔄'}
          </button>
          <button className="icon-button" onClick={() => setCurrentPage('alerts')}>🔔</button>
          <button className="icon-button" onClick={() => setCurrentPage('settings')}>⚙</button>
        </div>
      </header>

      <div className="app-layout">
        <nav className={`sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
          <ul className="nav-list">
            {navItems.map(item => (
              <li 
                key={item.id}
                className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
                onClick={() => setCurrentPage(item.id)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </li>
            ))}
          </ul>
          
          <div className="sidebar-footer">
            <div className="sidebar-device-count">
              <span>Devices</span>
              <strong>{totalCount}</strong>
            </div>
            <div className="sidebar-status">
              <span className="status-dot online"></span>
              <span>{onlineCount} online</span>
              <span className="status-dot critical" style={{ marginLeft: '8px' }}></span>
              <span>{criticalCount} critical</span>
            </div>
          </div>
        </nav>

        <main className={`main-content ${isSidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          {backendError && (
            <div className="mock-banner">
              ⚠ Cannot connect to backend at {API_BASE}. Please ensure the backend server is running.
            </div>
          )}

          {currentPage === 'dashboard' && renderDashboard()}
          {currentPage === 'devices' && (
            <DeviceManagement 
              devices={devices}
              branches={branches}
              onAddDevice={handleAddDevice}
              onEditDevice={handleEditDevice}
              onDeleteDevice={handleDeleteDevice}
            />
          )}
          {currentPage === 'agents' && (
            <AgentManagement branches={branches} />
          )}
          {currentPage === 'topology' && (
            <div className="page-content">
              <h2 className="page-title">🌐 Network Topology</h2>
              <NetworkTopology devices={devices} branches={branches} onNodeClick={handleNodeClick} />
            </div>
          )}
          {currentPage === 'alerts' && renderAlertsPage()}
          {currentPage === 'reports' && renderReportsPage()}
          {currentPage === 'settings' && renderSettingsPage()}
        </main>
      </div>

      {selectedAlert && (
        <div className="modal-overlay" onClick={() => setSelectedAlert(null)}>
          <div className="alert-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className={`severity-badge ${selectedAlert.severity?.toLowerCase()}`}>
                  {selectedAlert.severity || 'ALERT'}
                </span>
                <h2>{selectedAlert.title}</h2>
                <p>{selectedAlert.hostname} • {selectedAlert.ip_address}</p>
              </div>
              <button className="close-button" onClick={() => setSelectedAlert(null)}>×</button>
            </div>
            <div className="detail-section problem-section">
              <h3>⚠️ Problem Detail</h3>
              <p>{selectedAlert.problem}</p>
            </div>
            <div className="detail-section">
              <h3>🔍 Possible Cause</h3>
              <p>{selectedAlert.cause}</p>
            </div>
            <div className="detail-section solution-section">
              <h3>✅ Recommended Solution</h3>
              {Array.isArray(selectedAlert.solution) ? (
                <ol>
                  {selectedAlert.solution.map((step, i) => <li key={i}>{step}</li>)}
                </ol>
              ) : (
                <p>{selectedAlert.solution}</p>
              )}
            </div>
            <div className="modal-actions">
              <button onClick={() => setSelectedAlert(null)}>Close</button>
              <button className="resolve-button" onClick={() => setSelectedAlert(null)}>✅ Resolve</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;