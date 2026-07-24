// frontend/src/components/AgentManagement.jsx
import React, { useState, useEffect } from 'react';
import './AgentManagement.css';

const API_BASE = "http://127.0.0.1:8000/api/v1";

const AgentManagement = ({ branches }) => {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRole, setFilterRole] = useState('all');
  const [formData, setFormData] = useState({
    full_name: '',
    role: 'NETWORK_AGENT',
    email: '',
    phone_number: '',
    branch_id: '',
    is_active: true
  });

  // ============================================================
  // LOAD AGENTS
  // ============================================================
  const loadAgents = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/agents`);
      if (!response.ok) throw new Error('Failed to load agents');
      const data = await response.json();
      setAgents(data.agents || []);
    } catch (error) {
      console.error('Error loading agents:', error);
      showToast('❌ Failed to load agents', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  // ============================================================
  // ADD AGENT
  // ============================================================
  const handleAddAgent = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add agent');
      }

      await loadAgents();
      setShowModal(false);
      resetForm();
      showToast(`✅ Agent "${formData.full_name}" added successfully`, 'success');
    } catch (error) {
      showToast(`❌ ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // EDIT AGENT
  // ============================================================
  const handleEditAgent = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/agents/${editingAgent.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update agent');
      }

      await loadAgents();
      setShowModal(false);
      resetForm();
      showToast(`✅ Agent "${formData.full_name}" updated`, 'success');
    } catch (error) {
      showToast(`❌ ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // DELETE AGENT
  // ============================================================
  const handleDeleteAgent = async (agentId, agentName) => {
    if (!window.confirm(`Are you sure you want to delete agent "${agentName}"?`)) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/agents/${agentId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete agent');
      }

      await loadAgents();
      showToast(`🗑️ Agent "${agentName}" deleted`, 'info');
    } catch (error) {
      showToast(`❌ ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // FORM HANDLERS
  // ============================================================
  const resetForm = () => {
    setFormData({
      full_name: '',
      role: 'NETWORK_AGENT',
      email: '',
      phone_number: '',
      branch_id: '',
      is_active: true
    });
    setEditingAgent(null);
  };

  const handleEditClick = (agent) => {
    setEditingAgent(agent);
    setFormData({
      full_name: agent.full_name || '',
      role: agent.role || 'NETWORK_AGENT',
      email: agent.email || '',
      phone_number: agent.phone_number || '',
      branch_id: agent.branch_id || '',
      is_active: agent.is_active !== undefined ? agent.is_active : true
    });
    setShowModal(true);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
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
  // FILTERS
  // ============================================================
  const filteredAgents = agents.filter(agent => {
    const matchesSearch = agent.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          agent.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          agent.phone_number?.includes(searchTerm);
    const matchesRole = filterRole === 'all' || agent.role === filterRole;
    return matchesSearch && matchesRole;
  });

  // ============================================================
  // ROLE BADGE
  // ============================================================
  const getRoleBadge = (role) => {
    const roleMap = {
      'NETWORK_AGENT': { label: 'Network Agent', class: 'network_agent' },
      'SUPERVISOR': { label: 'Supervisor', class: 'supervisor' },
      'MANAGER': { label: 'Manager', class: 'manager' },
      'HEAD_OF_IT': { label: 'Head of IT', class: 'head_of_it' },
      'HELPDESK': { label: 'Helpdesk', class: 'helpdesk' },
    };
    return roleMap[role] || { label: role, class: 'unknown' };
  };

  // ============================================================
  // RENDER
  // ============================================================
  return (
    <div className="agent-management">
      {/* Header */}
      <div className="am-header">
        <div>
          <h2>
            <i className="fas fa-users" style={{ color: '#00b4d8' }}></i>
            Agent Management
          </h2>
          <p>{agents.length} agents • {branches?.length || 0} branches</p>
        </div>
        <button className="am-add-btn" onClick={() => { resetForm(); setShowModal(true); }} disabled={loading}>
          <i className="fas fa-plus"></i> {loading ? 'Processing...' : 'Add Agent'}
        </button>
      </div>

      {/* Search & Filter */}
      <div className="am-toolbar">
        <div className="am-search">
          <i className="fas fa-search"></i>
          <input
            type="text"
            placeholder="Search by name, email or phone..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="am-filter">
          <select value={filterRole} onChange={(e) => setFilterRole(e.target.value)}>
            <option value="all">All Roles</option>
            <option value="NETWORK_AGENT">🟦 Network Agent</option>
            <option value="SUPERVISOR">🟩 Supervisor</option>
            <option value="MANAGER">🟨 Manager</option>
            <option value="HEAD_OF_IT">🟪 Head of IT</option>
            <option value="HELPDESK">🟦 Helpdesk</option>
          </select>
        </div>
      </div>

      {/* Agent Table */}
      <div className="am-table-wrap">
        <table className="am-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Branch</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredAgents.length === 0 ? (
              <tr>
                <td colSpan="7" className="am-empty">No agents found</td>
              </tr>
            ) : (
              filteredAgents.map(agent => {
                const roleInfo = getRoleBadge(agent.role);
                const branchName = branches?.find(b => b.id === agent.branch_id)?.name || 'All Branches';
                
                return (
                  <tr key={agent.id}>
                    <td className="am-name">{agent.full_name}</td>
                    <td>
                      <span className={`role-badge ${roleInfo.class}`}>
                        {roleInfo.label}
                      </span>
                    </td>
                    <td className="am-email">{agent.email}</td>
                    <td className="am-phone">{agent.phone_number}</td>
                    <td>{branchName}</td>
                    <td>
                      <span className={`status-badge ${agent.is_active ? 'active' : 'inactive'}`}>
                        {agent.is_active ? '🟢 Active' : '🔴 Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="am-actions">
                        <button 
                          className="am-action-btn edit"
                          onClick={() => handleEditClick(agent)}
                          title="Edit"
                          disabled={loading}
                        >
                          <i className="fas fa-edit"></i>
                        </button>
                        <button 
                          className="am-action-btn delete"
                          onClick={() => handleDeleteAgent(agent.id, agent.full_name)}
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

      {/* Add/Edit Modal */}
      {showModal && (
        <div className="am-modal-overlay" onClick={() => setShowModal(false)}>
          <div className="am-modal" onClick={(e) => e.stopPropagation()}>
            <div className="am-modal-header">
              <h3>
                {editingAgent ? (
                  <><i className="fas fa-edit"></i> Edit Agent</>
                ) : (
                  <><i className="fas fa-user-plus"></i> Add Agent</>
                )}
              </h3>
              <button className="am-modal-close" onClick={() => { setShowModal(false); resetForm(); }}>×</button>
            </div>

            <form onSubmit={editingAgent ? handleEditAgent : handleAddAgent}>
              <div className="am-form-grid">
                <div className="am-form-group" style={{ gridColumn: 'span 2' }}>
                  <label>Full Name *</label>
                  <input
                    type="text"
                    name="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    required
                    placeholder="e.g. Abebe Kebede"
                  />
                </div>

                <div className="am-form-group">
                  <label>Role *</label>
                  <select name="role" value={formData.role} onChange={handleChange} required>
                    <option value="NETWORK_AGENT">🟦 Network Agent</option>
                    <option value="SUPERVISOR">🟩 Supervisor</option>
                    <option value="MANAGER">🟨 Manager</option>
                    <option value="HEAD_OF_IT">🟪 Head of IT</option>
                    <option value="HELPDESK">🟦 Helpdesk</option>
                  </select>
                </div>

                <div className="am-form-group">
                  <label>Status</label>
                  <select 
                    name="is_active" 
                    value={formData.is_active ? 'true' : 'false'} 
                    onChange={(e) => setFormData({...formData, is_active: e.target.value === 'true'})}
                  >
                    <option value="true">🟢 Active</option>
                    <option value="false">🔴 Inactive</option>
                  </select>
                </div>

                <div className="am-form-group">
                  <label>Email *</label>
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    placeholder="e.g. abebe.k@oic.com.et"
                  />
                </div>

                <div className="am-form-group">
                  <label>Phone Number *</label>
                  <input
                    type="text"
                    name="phone_number"
                    value={formData.phone_number}
                    onChange={handleChange}
                    required
                    placeholder="e.g. +251911234567"
                  />
                </div>

                <div className="am-form-group" style={{ gridColumn: 'span 2' }}>
                  <label>Branch (Leave blank for all branches)</label>
                  <select name="branch_id" value={formData.branch_id} onChange={handleChange}>
                    <option value="">All Branches</option>
                    {branches?.map(branch => (
                      <option key={branch.id} value={branch.id}>
                        {branch.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="am-form-actions">
                <button type="button" className="am-btn-cancel" onClick={() => { setShowModal(false); resetForm(); }}>
                  Cancel
                </button>
                <button type="submit" className="am-btn-submit" disabled={loading}>
                  {loading ? 'Saving...' : (editingAgent ? 'Update Agent' : 'Add Agent')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentManagement;