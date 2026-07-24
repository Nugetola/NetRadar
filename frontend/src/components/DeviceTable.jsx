function DeviceTable({ devices, loading }) {

    if (loading) {
        return (
            <div className="empty">
                Loading devices...
            </div>
        );
    }

    if (!devices || devices.length === 0) {
        return (
            <div className="empty">
                No devices found.
            </div>
        );
    }

    return (
        <div className="table-wrap">
            <table>

                <thead>
                    <tr>
                        <th>Hostname</th>
                        <th>IP Address</th>
                        <th>Type</th>
                        <th>Branch</th>
                        <th>VLAN</th>
                        <th>Status</th>
                        <th>Last Check</th>
                    </tr>
                </thead>

                <tbody>
                    {devices.map((device) => (

                        <tr key={device.id}>

                            <td>
                                <strong>
                                    {device.hostname}
                                </strong>
                            </td>

                            <td>
                                {device.ip_address}
                            </td>

                            <td>
                                {device.device_type}
                            </td>

                            <td>
                                {device.branch_id || "Not Assigned"}
                            </td>

                            <td>
                                {device.vlan_id || "-"}
                            </td>

                            <td>
                                <span
                                    className={`status ${device.status.toLowerCase()}`}
                                >
                                    {device.status}
                                </span>
                            </td>

                            <td>
                                {device.last_check
                                    ? new Date(device.last_check)
                                        .toLocaleString()
                                    : "Never"}
                            </td>

                        </tr>

                    ))}
                </tbody>

            </table>
        </div>
    );
}

export default DeviceTable;