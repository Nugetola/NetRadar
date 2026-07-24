// frontend/src/components/NetworkTopology.jsx
import React, { useEffect, useRef, useState, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import './NetworkTopology.css';

const NetworkTopology = ({ devices = [], branches = [], onNodeClick }) => {
  const [selectedNode, setSelectedNode] = useState(null);
  const [filter, setFilter] = useState('all');
  const [filterValue, setFilterValue] = useState('');
  const fgRef = useRef();

  // ============================================================
  // HELPER FUNCTIONS - MUST BE DEFINED BEFORE useMemo
  // ============================================================
  const getStatusColor = (status) => {
    const statusMap = {
      'UP': '#2ecc71',
      'ONLINE': '#2ecc71',
      'DOWN': '#ff4757',
      'CRITICAL': '#ff4757',
      'WARNING': '#f39c12',
      'UNSTABLE': '#f39c12',
      'UNKNOWN': '#7a8aa0',
    };
    return statusMap[status?.toUpperCase()] || '#7a8aa0';
  };

  const getCriticalitySize = (criticality) => {
    const sizeMap = {
      'HIGH': 10,
      'MEDIUM': 7,
      'LOW': 5,
    };
    return sizeMap[criticality?.toUpperCase()] || 6;
  };

  // ============================================================
  // BUILD GRAPH DATA - useMemo with helper functions (defined above)
  // ============================================================
  const graphData = useMemo(() => {
    if (!devices || devices.length === 0) {
      return { nodes: [], links: [] };
    }

    const nodes = [];
    const links = [];
    const nodeMap = new Map();
    const safeBranches = branches || [];

    // 1. Create branch nodes
    safeBranches.forEach((branch) => {
      const branchDevices = devices.filter(d => d.branch_id === branch.id);
      const upCount = branchDevices.filter(d => d.status === 'ONLINE' || d.status === 'UP').length;
      const totalCount = branchDevices.length;
      
      nodeMap.set(`branch-${branch.id}`, {
        id: `branch-${branch.id}`,
        name: branch.name,
        ip: branch.wan_gateway_ip || 'N/A',
        status: totalCount > 0 && upCount === totalCount ? 'ONLINE' : 
                totalCount > 0 && upCount === 0 ? 'CRITICAL' : 'WARNING',
        criticality: 'LOW',
        device_type: 'BRANCH',
        color: totalCount > 0 && upCount === totalCount ? '#2ecc71' :
               totalCount > 0 && upCount === 0 ? '#ff4757' : '#f39c12',
        size: 12,
        val: 12,
        isBranch: true,
        branch_id: branch.id,
        location: branch.region || 'Unknown',
        device_count: totalCount,
        up_count: upCount
      });
    });

    // 2. Create device nodes
    devices.forEach((device) => {
      const statusColor = getStatusColor(device.status);
      const criticalitySize = getCriticalitySize(device.criticality);
      
      const branch = safeBranches.find(b => b.id === device.branch_id);
      
      nodeMap.set(device.id, {
        id: device.id,
        name: device.hostname || device.ip_address,
        ip: device.ip_address,
        status: device.status || 'UNKNOWN',
        criticality: device.criticality || 'MEDIUM',
        device_type: device.device_type || 'Unknown',
        vlan_id: device.vlan_id,
        branch_id: device.branch_id,
        branch_name: branch?.name || 'Unknown',
        region: branch?.region || 'Unknown',
        color: statusColor,
        size: criticalitySize,
        val: criticalitySize,
        parent_switch_id: device.parent_switch_id,
        location: `${branch?.name || 'Unknown'} - ${device.vlan_id ? `VLAN ${device.vlan_id}` : 'No VLAN'}`
      });
    });

    // 3. Create links
    nodeMap.forEach((node) => {
      if (node.isBranch) {
        devices.forEach((device) => {
          if (device.branch_id === node.branch_id && nodeMap.has(device.id)) {
            links.push({
              source: node.id,
              target: device.id,
              color: '#9b59b6',
              width: 1,
              type: 'branch'
            });
          }
        });
      } else if (node.parent_switch_id && nodeMap.has(node.parent_switch_id)) {
        links.push({
          source: node.parent_switch_id,
          target: node.id,
          color: '#00b4d8',
          width: 2,
          type: 'network'
        });
      }
    });

    // 4. Add VLAN nodes
    const vlanMap = new Map();
    devices.forEach((device) => {
      if (device.vlan_id && !vlanMap.has(device.vlan_id)) {
        const branch = safeBranches.find(b => b.id === device.branch_id);
        vlanMap.set(device.vlan_id, {
          id: `vlan-${device.vlan_id}`,
          name: `VLAN ${device.vlan_id}`,
          ip: `VLAN ${device.vlan_id}`,
          status: 'UP',
          criticality: 'MEDIUM',
          device_type: 'VLAN',
          color: '#f39c12',
          size: 8,
          val: 8,
          isVlan: true,
          branch_name: branch?.name || 'Unknown',
          location: `${branch?.name || 'Unknown'} - VLAN ${device.vlan_id}`
        });
      }
    });

    // 5. Add all nodes
    const allNodes = [];
    nodeMap.forEach((node) => {
      if (!node.isVlan) {
        allNodes.push(node);
      }
    });
    
    vlanMap.forEach((vlanNode) => {
      allNodes.push(vlanNode);
      devices.forEach((d) => {
        if (d.vlan_id === parseInt(vlanNode.name.split(' ')[1]) && 
            d.device_type === 'SWITCH' && 
            nodeMap.has(d.id)) {
          links.push({
            source: nodeMap.get(d.id),
            target: vlanNode,
            color: '#f39c12',
            width: 1.5,
            type: 'vlan'
          });
        }
        if (d.vlan_id === parseInt(vlanNode.name.split(' ')[1]) && 
            d.device_type !== 'SWITCH' && 
            nodeMap.has(d.id)) {
          links.push({
            source: vlanNode,
            target: nodeMap.get(d.id),
            color: '#7a8aa0',
            width: 1,
            type: 'vlan-member'
          });
        }
      });
    });

    return { nodes: allNodes, links };
  }, [devices, branches]);

  // ============================================================
  // HANDLERS
  // ============================================================
  const handleNodeClick = (node) => {
    setSelectedNode(node);
    if (onNodeClick) {
      onNodeClick(node);
    }
  };

  // ============================================================
  // FILTERING
  // ============================================================
  const getFilteredNodes = () => {
    if (filter === 'all') return graphData.nodes;
    
    if (filter === 'branch') {
      return graphData.nodes.filter(n => 
        n.branch_id === filterValue || n.branch_name === filterValue
      );
    }
    
    if (filter === 'vlan') {
      return graphData.nodes.filter(n => 
        n.vlan_id === parseInt(filterValue) || n.name === `VLAN ${filterValue}`
      );
    }
    
    return graphData.nodes;
  };

  const filteredNodes = getFilteredNodes();
  const filteredLinks = graphData.links.filter(link => {
    const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
    const targetId = typeof link.target === 'object' ? link.target.id : link.target;
    return filteredNodes.some(n => n.id === sourceId) &&
           filteredNodes.some(n => n.id === targetId);
  });

  // Get unique VLANs for filter
  const uniqueVlans = [...new Set(devices.filter(d => d.vlan_id).map(d => d.vlan_id))].sort();

  // ============================================================
  // RENDER
  // ============================================================
  if (graphData.nodes.length === 0) {
    return (
      <div className="topology-empty">
        <i className="fas fa-network-wired" style={{ fontSize: 48, color: '#7a8aa0' }}></i>
        <p>No devices found. Add devices to see network topology.</p>
      </div>
    );
  }

  return (
    <div className="network-topology-container">
      {/* Header */}
      <div className="topology-header">
        <div>
          <h3>
            <i className="fas fa-network-wired" style={{ color: '#00b4d8' }}></i>
            Network Topology
          </h3>
          <p className="topology-subtitle">
            {graphData.nodes.length} nodes • {(branches || []).length} branches • 
            {uniqueVlans.length} VLANs
          </p>
        </div>
        
        <div className="topology-controls">
          <select 
            className="topology-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All Nodes</option>
            <option value="branch">By Branch</option>
            <option value="vlan">By VLAN</option>
          </select>
          
          {filter === 'branch' && (
            <select 
              className="topology-filter"
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
            >
              <option value="">Select Branch</option>
              {(branches || []).map(b => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          )}
          
          {filter === 'vlan' && (
            <select 
              className="topology-filter"
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
            >
              <option value="">Select VLAN</option>
              {uniqueVlans.map(v => (
                <option key={v} value={v}>VLAN {v}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="topology-legend">
        <span><span className="legend-dot" style={{ background: '#2ecc71' }}></span> Online</span>
        <span><span className="legend-dot" style={{ background: '#ff4757' }}></span> Critical</span>
        <span><span className="legend-dot" style={{ background: '#f39c12' }}></span> Warning</span>
        <span><span className="legend-dot" style={{ background: '#00b4d8' }}></span> Switch</span>
        <span><span className="legend-dot" style={{ background: '#9b59b6' }}></span> Branch</span>
        <span><span className="legend-dot" style={{ background: '#f39c12' }}></span> VLAN</span>
        <span className="legend-info">
          <i className="fas fa-info-circle"></i> Click node for details
        </span>
      </div>

      {/* Graph */}
      <div className="topology-graph-wrapper">
        <ForceGraph2D
          ref={fgRef}
          graphData={{ nodes: filteredNodes, links: filteredLinks }}
          nodeLabel={(node) => `
            ${node.name}
            IP: ${node.ip || 'N/A'}
            Status: ${node.status || 'UNKNOWN'}
            Type: ${node.device_type || 'Unknown'}
            ${node.branch_name ? `Branch: ${node.branch_name}` : ''}
            ${node.vlan_id ? `VLAN: ${node.vlan_id}` : ''}
            ${node.location ? `Location: ${node.location}` : ''}
            ${node.device_count ? `Devices: ${node.device_count} (${node.up_count || 0} up)` : ''}
          `}
          nodeColor={(node) => node.color || '#7a8aa0'}
          nodeVal={(node) => node.val || 5}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.name;
            const fontSize = 10/globalScale;
            ctx.font = `${fontSize}px Inter, sans-serif`;
            
            const size = (node.val || 5) * globalScale;
            
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.color || '#7a8aa0';
            ctx.fill();
            
            ctx.strokeStyle = '#1a2a4a';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            
            if (node.status === 'CRITICAL' || node.status === 'DOWN') {
              ctx.shadowColor = '#ff4757';
              ctx.shadowBlur = 20;
              ctx.beginPath();
              ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI, false);
              ctx.fillStyle = 'rgba(255, 71, 87, 0.15)';
              ctx.fill();
              ctx.shadowBlur = 0;
            }
            
            if (node.isBranch) {
              ctx.font = `${fontSize * 1.2}px Inter, sans-serif`;
              ctx.fillStyle = '#ffffff';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillText('🏢', node.x, node.y);
            }
            
            if (node.isVlan) {
              ctx.font = `${fontSize * 1.2}px Inter, sans-serif`;
              ctx.fillStyle = '#ffffff';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillText('🌊', node.x, node.y);
            }
            
            ctx.fillStyle = '#e8edf3';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.font = `${fontSize}px Inter, sans-serif`;
            
            const displayLabel = label.length > 15 ? label.substring(0, 13) + '..' : label;
            ctx.fillText(displayLabel, node.x, node.y - size - 4);
            
            if (node.isBranch && node.location) {
              ctx.fillStyle = '#7a8aa0';
              ctx.font = `${fontSize * 0.8}px Inter, sans-serif`;
              ctx.fillText(node.location, node.x, node.y + size + 14);
            }
          }}
          linkColor={(link) => link.color || '#4a5a7a'}
          linkWidth={(link) => link.width || 1}
          linkDirectionalParticles={(link) => {
            if (link.type === 'network') return 3;
            if (link.type === 'vlan') return 2;
            return 1;
          }}
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleSpeed={0.005}
          onNodeClick={handleNodeClick}
          cooldownTicks={100}
          d3AlphaDecay={0.005}
          d3VelocityDecay={0.2}
          width={window.innerWidth - 100}
          height={500}
        />
      </div>

      {/* Stats */}
      <div className="topology-stats">
        <div>
          <span>Total Nodes</span>
          <strong>{graphData.nodes.length}</strong>
        </div>
        <div>
          <span>Branches</span>
          <strong>{(branches || []).length}</strong>
        </div>
        <div>
          <span>Switches</span>
          <strong>{devices.filter(d => d.device_type === 'SWITCH').length}</strong>
        </div>
        <div>
          <span>VLANs</span>
          <strong>{uniqueVlans.length}</strong>
        </div>
        <div>
          <span>Online</span>
          <strong style={{ color: '#2ecc71' }}>
            {devices.filter(d => d.status === 'ONLINE' || d.status === 'UP').length}
          </strong>
        </div>
        <div>
          <span>Critical</span>
          <strong style={{ color: '#ff4757' }}>
            {devices.filter(d => d.status === 'CRITICAL' || d.status === 'DOWN').length}
          </strong>
        </div>
      </div>

      {/* Node Details Modal */}
      {selectedNode && (
        <div className="topology-modal" onClick={() => setSelectedNode(null)}>
          <div className="topology-modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="topology-modal-close" onClick={() => setSelectedNode(null)}>×</button>
            
            <div className="topology-modal-header">
              <h3>{selectedNode.name}</h3>
              <span className={`status-badge ${selectedNode.status?.toLowerCase()}`}>
                {selectedNode.status || 'UNKNOWN'}
              </span>
            </div>
            
            <div className="topology-modal-details">
              <div>
                <label>IP Address</label>
                <span>{selectedNode.ip || 'N/A'}</span>
              </div>
              <div>
                <label>Device Type</label>
                <span>{selectedNode.device_type || 'Unknown'}</span>
              </div>
              <div>
                <label>Criticality</label>
                <span className={`criticality-tag ${selectedNode.criticality?.toLowerCase()}`}>
                  {selectedNode.criticality || 'MEDIUM'}
                </span>
              </div>
              <div>
                <label>Branch</label>
                <span>{selectedNode.branch_name || 'Unknown'}</span>
              </div>
              <div>
                <label>VLAN</label>
                <span>{selectedNode.vlan_id || 'N/A'}</span>
              </div>
              <div>
                <label>Location</label>
                <span>{selectedNode.location || 'Unknown'}</span>
              </div>
              {selectedNode.isBranch && (
                <>
                  <div>
                    <label>Devices</label>
                    <span>{selectedNode.device_count || 0}</span>
                  </div>
                  <div>
                    <label>Online</label>
                    <span style={{ color: '#2ecc71' }}>{selectedNode.up_count || 0}</span>
                  </div>
                </>
              )}
              {selectedNode.parent_switch_id && (
                <div>
                  <label>Parent Switch</label>
                  <span>{selectedNode.parent_switch_id}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NetworkTopology;