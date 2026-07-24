const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

async function request(endpoint, options = {}) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Request failed");
    }

    return response.json();
}

export const api = {
    // Dashboard
    getSummary: () =>
        request("/dashboard/summary"),

    // Devices
    getDevices: () =>
        request("/devices"),

    createDevice: (device) =>
        request("/devices", {
            method: "POST",
            body: JSON.stringify(device)
        }),

    updateDevice: (id, device) =>
        request(`/devices/${id}`, {
            method: "PUT",
            body: JSON.stringify(device)
        }),

    deleteDevice: (id) =>
        request(`/devices/${id}`, {
            method: "DELETE"
        }),

    // Branches
    getBranches: () =>
        request("/branches"),

    createBranch: (branch) =>
        request("/branches", {
            method: "POST",
            body: JSON.stringify(branch)
        }),

    getBranchesByRegion: (region) =>
        request(`/branches/?region=${encodeURIComponent(region)}`),

    getRegionStats: () =>
        request("/branches/regions/stats"),

    // ============================================================
    // DIRECTORATES (NEW)
    // ============================================================
    getDirectorates: () =>
        request("/directorates"),

    createDirectorate: (directorate) =>
        request("/directorates", {
            method: "POST",
            body: JSON.stringify(directorate)
        }),

    // ============================================================
    // AGENTS
    // ============================================================
    getAgents: () =>
        request("/agents"),

    createAgent: (agent) =>
        request("/agents", {
            method: "POST",
            body: JSON.stringify(agent)
        }),

    // ============================================================
    // TICKETS
    // ============================================================
    getTickets: () =>
        request("/tickets"),

    createTicket: (ticket) =>
        request("/tickets", {
            method: "POST",
            body: JSON.stringify(ticket)
        }),

    updateTicket: (id, ticket) =>
        request(`/tickets/${id}`, {
            method: "PUT",
            body: JSON.stringify(ticket)
        }),

    // ============================================================
    // STATISTICS
    // ============================================================
    getStatistics: (region = null) => {
        const url = region 
            ? `/statistics/?region=${encodeURIComponent(region)}`
            : "/statistics";
        return request(url);
    },

    getRegionDashboard: (region) =>
        request(`/branches/regions/${encodeURIComponent(region)}/dashboard`),

    // ============================================================
    // VLAN PROFILES
    // ============================================================
    getVlanProfiles: () =>
        request("/vlan-profiles"),

    createVlanProfile: (profile) =>
        request("/vlan-profiles", {
            method: "POST",
            body: JSON.stringify(profile)
        }),
};