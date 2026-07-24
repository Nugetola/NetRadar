// frontend/src/components/AddDeviceForm.jsx
import { useEffect, useState } from "react";
import { api } from "../api/api";
import "./AddDeviceForm.css";

function AddDeviceForm({ onCreated, onCancel, initialData = null }) {

    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState("");
    const [messageType, setMessageType] = useState("success");

    // Branches
    const [branches, setBranches] = useState([]);

    // Head Office Directorates
    const [directorates, setDirectorates] = useState([]);

    // Parent Switches
    const [switches, setSwitches] = useState([]);

    // Branch or Head Office
    const [orgType, setOrgType] = useState("branch");

    const [form, setForm] = useState({
        hostname: "",
        ip_address: "",
        device_type: "PC",
        criticality: "MEDIUM",
        vlan_id: "",
        subnet: "",
        branch_id: "",
        directorate_id: "",
        parent_switch_id: ""
    });

    // Load initial data if editing
    useEffect(() => {
        if (initialData) {
            setForm({
                hostname: initialData.hostname || "",
                ip_address: initialData.ip_address || "",
                device_type: initialData.device_type || "PC",
                criticality: initialData.criticality || "MEDIUM",
                vlan_id: initialData.vlan_id || "",
                subnet: initialData.subnet || "",
                branch_id: initialData.branch_id || "",
                directorate_id: initialData.directorate_id || "",
                parent_switch_id: initialData.parent_switch_id || ""
            });
            setOrgType(initialData.orgType || (initialData.branch_id ? "branch" : "directorate"));
        }
    }, [initialData]);

    useEffect(() => {
        loadBranches();
        loadDirectorates();
        loadSwitches();
    }, []);

    // =====================================================
    // Load Branches
    // =====================================================
    async function loadBranches() {
        try {
            const result = await api.getBranches();
            if (result.branches) {
                setBranches(result.branches);
            } else if (Array.isArray(result)) {
                setBranches(result);
            } else {
                setBranches([]);
            }
        } catch (err) {
            console.error(err);
            setBranches([]);
        }
    }

    // =====================================================
    // Load Head Office Directorates
    // =====================================================
    async function loadDirectorates() {
        try {
            const result = await api.getDirectorates();
            let dirs = [];
            if (result.directorates) {
                dirs = result.directorates;
            } else if (Array.isArray(result)) {
                dirs = result;
            }
            setDirectorates(dirs);
        } catch (err) {
            console.error(err);
            setDirectorates([]);
        }
    }

    // =====================================================
    // Load Parent Switches
    // =====================================================
    async function loadSwitches() {
        try {
            const devices = await api.getDevices();
            const onlySwitches = devices.devices?.filter(d => d.device_type === "SWITCH") || [];
            setSwitches(onlySwitches);
        } catch (err) {
            console.error(err);
            setSwitches([]);
        }
    }

    // =====================================================
    // Handle Input Change
    // =====================================================
    function handleChange(e) {
        const { name, value } = e.target;
        setForm(prev => ({
            ...prev,
            [name]: value
        }));
    }

    // =====================================================
    // Organization Type
    // =====================================================
    function handleOrgType(type) {
        setOrgType(type);
        setForm(prev => ({
            ...prev,
            branch_id: "",
            directorate_id: ""
        }));
    }

    // =====================================================
    // Submit
    // =====================================================
    async function handleSubmit(e) {
        e.preventDefault();
        setLoading(true);
        setMessage("");
        setMessageType("success");

        try {
            // Validate
            if (!form.hostname.trim()) {
                throw new Error("Hostname is required");
            }
            if (!form.ip_address.trim()) {
                throw new Error("IP Address is required");
            }
            if (orgType === "branch" && !form.branch_id) {
                throw new Error("Please select a Branch");
            }
            if (orgType === "directorate" && !form.directorate_id) {
                throw new Error("Please select a Directorate/Office");
            }

            const payload = {
                hostname: form.hostname.trim(),
                ip_address: form.ip_address.trim(),
                device_type: form.device_type,
                criticality: form.criticality,
                vlan_id: form.vlan_id ? Number(form.vlan_id) : null,
                subnet: form.subnet || null,
                parent_switch_id: form.parent_switch_id || null,
                is_active: true,
                current_status: "UNKNOWN",
            };

            if (orgType === "branch") {
                payload.branch_id = form.branch_id;
                payload.directorate_id = null;
            } else {
                if (form.directorate_id === "head-office") {
                    payload.directorate_id = null;
                    payload.branch_id = null;
                } else {
                    payload.directorate_id = form.directorate_id;
                    payload.branch_id = null;
                }
            }

            await api.createDevice(payload);

            setMessageType("success");
            setMessage("✅ Device added successfully!");

            // Reset form
            setForm({
                hostname: "",
                ip_address: "",
                device_type: "PC",
                criticality: "MEDIUM",
                vlan_id: "",
                subnet: "",
                branch_id: "",
                directorate_id: "",
                parent_switch_id: ""
            });
            setOrgType("branch");

            if (onCreated) {
                onCreated(payload);
            }

        } catch (err) {
            setMessageType("error");
            setMessage("❌ " + err.message);
        } finally {
            setLoading(false);
        }
    }

    // =====================================================
    // UI
    // =====================================================
    return (
        <form className="adf-form" onSubmit={handleSubmit}>
            {/* Message */}
            {message && (
                <div className={`adf-message adf-message-${messageType}`}>
                    {message}
                </div>
            )}

            {/* ============================================= */}
            {/* Row 1: Hostname + IP Address */}
            {/* ============================================= */}
            <div className="adf-row">
                <div className="adf-group">
                    <label className="adf-label">
                        <span className="adf-required">*</span> Hostname
                    </label>
                    <input
                        type="text"
                        name="hostname"
                        className="adf-input"
                        placeholder="e.g. OIC-HQ-SRV01"
                        value={form.hostname}
                        onChange={handleChange}
                        required
                    />
                </div>
                <div className="adf-group">
                    <label className="adf-label">
                        <span className="adf-required">*</span> IP Address
                    </label>
                    <input
                        type="text"
                        name="ip_address"
                        className="adf-input"
                        placeholder="e.g. 192.168.1.100"
                        value={form.ip_address}
                        onChange={handleChange}
                        required
                    />
                </div>
            </div>

            {/* ============================================= */}
            {/* Row 2: Device Type + Criticality */}
            {/* ============================================= */}
            <div className="adf-row">
                <div className="adf-group">
                    <label className="adf-label">Device Type</label>
                    <select
                        name="device_type"
                        className="adf-select"
                        value={form.device_type}
                        onChange={handleChange}
                    >
                        <option value="SWITCH">🔀 Switch</option>
                        <option value="ROUTER">🌐 Router</option>
                        <option value="SERVER">🖥️ Server</option>
                        <option value="FIREWALL">🛡️ Firewall</option>
                        <option value="ACCESS_POINT">📡 Access Point</option>
                        <option value="PC">💻 PC</option>
                        <option value="PRINTER">🖨️ Printer</option>
                    </select>
                </div>
                <div className="adf-group">
                    <label className="adf-label">Criticality</label>
                    <select
                        name="criticality"
                        className="adf-select"
                        value={form.criticality}
                        onChange={handleChange}
                    >
                        <option value="LOW">🟢 LOW</option>
                        <option value="MEDIUM">🟡 MEDIUM</option>
                        <option value="HIGH">🔴 HIGH</option>
                        <option value="CRITICAL">🚨 CRITICAL</option>
                    </select>
                </div>
            </div>

            {/* ============================================= */}
            {/* Row 3: VLAN + Subnet */}
            {/* ============================================= */}
            <div className="adf-row">
                <div className="adf-group">
                    <label className="adf-label">VLAN ID</label>
                    <input
                        type="number"
                        name="vlan_id"
                        className="adf-input"
                        placeholder="e.g. 10"
                        min="1"
                        max="4094"
                        value={form.vlan_id}
                        onChange={handleChange}
                    />
                </div>
                <div className="adf-group">
                    <label className="adf-label">Subnet</label>
                    <input
                        type="text"
                        name="subnet"
                        className="adf-input"
                        placeholder="e.g. 192.168.1.0/24"
                        value={form.subnet}
                        onChange={handleChange}
                    />
                </div>
            </div>

            {/* ============================================= */}
            {/* Organization Unit */}
            {/* ============================================= */}
            <div className="adf-org-section">
                <label className="adf-label adf-org-label">
                    <span className="adf-required">*</span> Organization Unit
                </label>

                <div className="adf-org-radio-group">
                    <label className={`adf-org-radio ${orgType === "branch" ? "active" : ""}`}>
                        <input
                            type="radio"
                            checked={orgType === "branch"}
                            onChange={() => handleOrgType("branch")}
                        />
                        <span className="adf-org-icon">🏢</span>
                        Branch
                    </label>
                    <label className={`adf-org-radio ${orgType === "directorate" ? "active" : ""}`}>
                        <input
                            type="radio"
                            checked={orgType === "directorate"}
                            onChange={() => handleOrgType("directorate")}
                        />
                        <span className="adf-org-icon">🏛️</span>
                        Head Office
                    </label>
                </div>

                {/* Branch Dropdown */}
                {orgType === "branch" && (
                    <div className="adf-group adf-org-dropdown">
                        <label className="adf-label">Select Branch</label>
                        <select
                            name="branch_id"
                            className="adf-select"
                            value={form.branch_id}
                            onChange={handleChange}
                            required
                        >
                            <option value="">— Select Branch —</option>
                            {branches.map(branch => (
                                <option key={branch.id} value={branch.id}>
                                    {branch.name}
                                </option>
                            ))}
                        </select>
                    </div>
                )}

                {/* Directorate Dropdown */}
                {orgType === "directorate" && (
                    <div className="adf-group adf-org-dropdown">
                        <label className="adf-label">Select Directorate/Office</label>
                        <select
                            name="directorate_id"
                            className="adf-select"
                            value={form.directorate_id}
                            onChange={handleChange}
                            required
                        >
                            <option value="">— Select Directorate —</option>
                            {directorates.map(dept => (
                                <option key={dept.id} value={dept.id}>
                                    {dept.name}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
            </div>

            {/* ============================================= */}
            {/* Parent Switch */}
            {/* ============================================= */}
            <div className="adf-group">
                <label className="adf-label">Parent Switch</label>
                <select
                    name="parent_switch_id"
                    className="adf-select"
                    value={form.parent_switch_id}
                    onChange={handleChange}
                >
                    <option value="">— None (Core Device) —</option>
                    {switches.map(sw => (
                        <option key={sw.id} value={sw.id}>
                            {sw.hostname} ({sw.ip_address})
                        </option>
                    ))}
                </select>
            </div>

            {/* ============================================= */}
            {/* Buttons */}
            {/* ============================================= */}
            <div className="adf-actions">
                {onCancel && (
                    <button
                        type="button"
                        className="adf-btn adf-btn-secondary"
                        onClick={onCancel}
                        disabled={loading}
                    >
                        Cancel
                    </button>
                )}
                <button
                    type="submit"
                    className="adf-btn adf-btn-primary"
                    disabled={loading}
                >
                    {loading ? (
                        <>
                            <span className="adf-spinner"></span>
                            Saving...
                        </>
                    ) : (
                        <>
                            <span>➕</span> {initialData ? "Update Device" : "Add Device"}
                        </>
                    )}
                </button>
            </div>
        </form>
    );
}

export default AddDeviceForm;