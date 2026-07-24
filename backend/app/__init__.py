def __init__(
    self,
    db_session_factory,
    websocket_manager=None,
    diagnostic_engine=None,
    snmp_service=None,
    poll_interval=60,
    debounce_window=180
):
    self.db_session_factory = db_session_factory
    self.websocket_manager = websocket_manager
    self.diagnostic_engine = (
        diagnostic_engine
        or DiagnosticEngine()
    )

    self.snmp_service = (
        snmp_service
        or SNMPService(
            community="public"
        )
    )

    self.poll_interval = poll_interval
    self.debounce_window = debounce_window