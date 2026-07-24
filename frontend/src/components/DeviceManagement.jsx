// frontend/src/components/DeviceManagement.jsx
import React, { useState } from 'react';
import AddDeviceForm from './AddDeviceForm';
import './DeviceManagement.css';

const API_BASE = "http://127.0.0.1:8000/api/v1";

const DeviceManagement = ({ devices, branches, onAddDevice, onEditDevice, onDeleteDevice }) => {
  const [showModal, setShowModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');

  // ============================================================
  // ADD DEVICE - API Call
  // ============================================================
  const handleAddDevice = async (deviceData) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/devices`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          hostname: deviceData.hostname,
          ip_address: deviceData.ip_address,
          device_type: deviceData.device_type,
          criticality: deviceData.criticality,
          vlan_id: deviceData.vlan_id ? parseInt(deviceData.vlan_id) : null,
          subnet: deviceData.subnet || null,
          branch_id: deviceData.branch_id || null,
          directorate_id: deviceData.directorate_id || null,
          parent_switch_id: deviceData.parent_switch_id || null,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add device');
      }

      const newDevice = await response.json();
      
      onAddDevice({
        id: newDevice.id,
        hostname: newDevice.hostname,
        ip_address: newDevice.ip_address,
        device_type: newDevice.device_type,
        criticality: newDevice.criticality,
        vlan_id: newDevice.vlan_id,
        branch_id: newDevice.branch_id,
        directorate_id: newDevice.directorate_id,
        parent_switch_id: newDevice.parent_switch_id,
        status: 'UNKNOWN',
        latency_ms: null,
        packet_loss: 0,
        last_check: new Date().toISOString(),
      });

      setShowModal(false);
      showToast(`✅ Device "${deviceData.hostname}" added successfully`, 'success');
      
    } catch (error) {
      console.error('Error adding device:', error);
      showToast(`❌ Failed to add device: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // EDIT DEVICE - API Call
  // ============================================================
  const handleEditDevice = async (deviceId, deviceData) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/devices/${deviceId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          hostname: deviceData.hostname,
          ip_address: deviceData.ip_address,
          device_type: deviceData.device_type,
          criticality: deviceData.criticality,
          vlan_id: deviceData.vlan_id ? parseInt(deviceData.vlan_id) : null,
          subnet: deviceData.subnet || null,
          branch_id: deviceData.branch_id || null,
          directorate_id: deviceData.directorate_id || null,
          parent_switch_id: deviceData.parent_switch_id || null,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update device');
      }

      const updatedDevice = await response.json();
      
      onEditDevice({
        ...updatedDevice,
        status: updatedDevice.status || 'UNKNOWN',
        latency_ms: updatedDevice.latency_ms || null,
        packet_loss: updatedDevice.packet_loss || 0,
        last_check: new Date().toISOString(),
      });

      setShowModal(false);
      showToast(`✅ Device "${deviceData.hostname}" updated`, 'success');
      
    } catch (error) {
      console.error('Error updating device:', error);
      showToast(`❌ Failed to update device: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // DELETE DEVICE - API Call
  // ============================================================
  const handleDeleteDevice = async (deviceId, hostname) => {
    if (!window.confirm(`Are you sure you want to delete device "${hostname}"?`)) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/devices/${deviceId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete device');
      }

      onDeleteDevice(deviceId);
      showToast(`🗑️ Device "${hostname}" deleted`, 'info');
      
    } catch (error) {
      console.error('Error deleting device:', error);
      showToast(`❌ Failed to delete device: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // TOAST NOTIFICATION
  // ============================================================
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
  // HANDLERS
  // ============================================================
  const handleAddClick = () => {
    setEditingDevice(null);
    setShowModal(true);
  };

  const handleEditClick = (device) => {
    setEditingDevice(device);
    setShowModal(true);
  };

  const handleFormSubmit = (deviceData) => {
    if (editingDevice) {
      handleEditDevice(editingDevice.id, deviceData);
    } else {
      handleAddDevice(deviceData);
    }
  };

  // Filter devices
  const filteredDevices = devices.filter(device => {
    const matchesSearch = device.hostname?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          device.ip_address?.includes(searchTerm);
    const matchesType = filterType === 'all' || device.device_type === filterType;
    return matchesSearch && matchesType;
  });

  const getStatusColor = (status) => {
    const colors = {
      'ONLINE': '#2ecc71',
      'CRITICAL': '#ff4757',
      'WARNING': '#f39c12',
      'UNKNOWN': '#7a8aa0',
    };
    return colors[status?.toUpperCase()] || '#7a8aa0';
  };

  const getCriticalityClass = (criticality) => {
    return criticality?.toLowerCase() || 'medium';
  };

  return (
    <div className="device-management">
      {/* Header */}
      <div className="dm-header">
        <div>
          <h2>
            <i className="fas fa-server" style={{ color: '#00b4d8' }}></i>
            Device Management
          </h2>
          <p>{devices.length} devices • {branches.length} branches</p>
        </div>
        <button className="dm-add-btn" onClick={handleAddClick} disabled={loading}>
          <i className="fas fa-plus"></i> {loading ? 'Processing...' : 'Add Device'}
        </button>
      </div>

      {/* Search & Filter */}
      <div className="dm-toolbar">
        <div className="dm-search">
          <i className="fas fa-search"></i>
          <input
            type="text"
            placeholder="Search by hostname or IP..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="dm-filter">
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
            <option value="all">All Types</option>
            <option value="SWITCH">🔄 Switch</option>
            <option value="ROUTER">🌐 Router</option>
            <option value="SERVER">🖥️ Server</option>
            <option value="PC">💻 PC</option>
            <option value="PRINTER">🖨️ Printer</option>
          </select>
        </div>
      </div>

      {/* Device Table */}
      <div className="dm-table-wrap">
        <table className="dm-table">
          <thead>
            <tr>
              <th>Device</th>
              <th>IP Address</th>
              <th>Type</th>
              <th>Status</th>
              <th>Criticality</th>
              <th>VLAN</th>
              <th>Organization</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredDevices.length === 0 ? (
              <tr>
                <td colSpan="8" className="dm-empty">No devices found</td>
              </tr>
            ) : (
              filteredDevices.map(device => {
                // Get organization name
                let orgName = '—';
                let orgIcon = '';
                if (device.branch_id) {
                  const branch = branches.find(b => b.id === device.branch_id);
                  orgName = branch?.name || '—';
                  orgIcon = '🏢 ';
                } else if (device.directorate_id) {
                  orgName = device.organization || device.directorate_name || '—';
                  orgIcon = '🏛️ ';
                }

                return (
                  <tr key={device.id}>
                    <td className="dm-device-name">{device.hostname}</td>
                    <td className="dm-ip">{device.ip_address}</td>
                    <td>
                      <span className="dm-type-tag">{device.device_type || 'Unknown'}</span>
                    </td>
                    <td>
                      <span 
                        className="dm-status-dot" 
                        style={{ background: getStatusColor(device.status) }}
                      ></span>
                      <span className="dm-status-text">{device.status || 'UNKNOWN'}</span>
                    </td>
                    <td>
                      <span className={`dm-criticality-tag ${getCriticalityClass(device.criticality)}`}>
                        {device.criticality || 'MEDIUM'}
                      </span>
                    </td>
                    <td>{device.vlan_id || '—'}</td>
                    <td className="dm-branch-name">
                      {orgIcon}{orgName}
                    </td>
                    <td>
                      <div className="dm-actions">
                        <button 
                          className="dm-action-btn edit"
                          onClick={() => handleEditClick(device)}
                          title="Edit"
                          disabled={loading}
                        >
                          <i className="fas fa-edit"></i>
                        </button>
                        <button 
                          className="dm-action-btn delete"
                          onClick={() => handleDeleteDevice(device.id, device.hostname)}
                          title="Delete"
                          disabled={loading}
                        >
                          <i className="fas fa-trash"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Add/Edit Modal - Using AddDeviceForm */}
      {showModal && (
        <div className="dm-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="dm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="dm-modal-header">
              <h3>
                {editingDevice ? (
                  <><i className="fas fa-edit"></i> Edit Device</>
                ) : (
                  <><i className="fas fa-plus"></i> Add Device</>
                )}
              </h3>
              <button className="dm-modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>

            <div className="dm-modal-body">
              <AddDeviceForm
                onCreated={(newDevice) => {
                  if (editingDevice) {
                    handleEditDevice(editingDevice.id, newDevice);
                  } else {
                    handleAddDevice(newDevice);
                  }
                }}
                onCancel={() => {
                  setShowModal(false);
                  setEditingDevice(null);
                }}
                initialData={editingDevice ? {
                  hostname: editingDevice.hostname,
                  ip_address: editingDevice.ip_address,
                  device_type: editingDevice.device_type,
                  criticality: editingDevice.criticality,
                  vlan_id: editingDevice.vlan_id,
                  subnet: editingDevice.subnet,
                  branch_id: editingDevice.branch_id,
                  directorate_id: editingDevice.directorate_id,
                  parent_switch_id: editingDevice.parent_switch_id,
                  orgType: editingDevice.branch_id ? 'branch' : 'directorate',
                } : null}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DeviceManagement;