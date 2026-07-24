function SummaryCards({ summary }) {
    if (!summary) {
        return (
            <div className="summary">
                <div className="metric loading">Loading...</div>
                <div className="metric loading">Loading...</div>
                <div className="metric loading">Loading...</div>
                <div className="metric loading">Loading...</div>
            </div>
        );
    }

    return (
        <div className="summary">

            <div className="metric">
                <span>Total Devices</span>
                <b>{summary.total_devices}</b>
            </div>

            <div className="metric">
                <span>Devices UP</span>
                <b className="green">
                    {summary.devices_status?.UP || 0}
                </b>
            </div>

            <div className="metric">
                <span>Devices DOWN</span>
                <b className="red">
                    {summary.devices_status?.DOWN || 0}
                </b>
            </div>

            <div className="metric">
                <span>Open Tickets</span>
                <b className="amber">
                    {summary.open_tickets}
                </b>
            </div>

        </div>
    );
}

export default SummaryCards;