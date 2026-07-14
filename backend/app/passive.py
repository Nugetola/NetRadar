"""Passive UDP event receivers for Syslog and SNMP traps.

The trap receiver intentionally preserves raw packets until vendor MIBs and
SNMPv3 credentials are approved. This prevents unauthenticated trap text from
being treated as trusted root-cause data.
"""
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from .config import get_settings
from .database import SessionLocal
from .models import Device, DeviceStatusLog
from .realtime import manager

log = logging.getLogger(__name__)


def _allowed(ip: str) -> bool:
    sources = {entry.strip() for entry in get_settings().passive_source_allowlist.split(",") if entry.strip()}
    return not sources or ip in sources


class PassiveProtocol(asyncio.DatagramProtocol):
    def __init__(self, event_kind: str):
        self.event_kind = event_kind

    def datagram_received(self, data: bytes, addr):
        source_ip, _ = addr
        if not _allowed(source_ip):
            log.warning("Rejected %s packet from untrusted source %s", self.event_kind, source_ip)
            return
        asyncio.create_task(self._record(source_ip, data))

    async def _record(self, source_ip: str, data: bytes) -> None:
        preview = data.decode("utf-8", errors="replace")[:2000] if self.event_kind == "SYSLOG" else data[:512].hex()
        async with SessionLocal() as session:
            device = await session.scalar(select(Device).where(Device.ip_address == source_ip))
            if device:
                payload = {"source_ip": source_ip, "event_kind": self.event_kind, "raw_preview": preview}
                session.add(DeviceStatusLog(device_id=device.id, status=device.current_status, failure_reason=f"PASSIVE_{self.event_kind}", diagnostics=payload))
                await session.commit()
            await manager.broadcast({
                "event_type": "PASSIVE_NETWORK_EVENT", "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_info": {"id": device.id if device else None, "ip_address": source_ip, "hostname": device.hostname if device else "Unregistered source", "status": device.current_status if device else "UNKNOWN", "criticality_level": device.criticality if device else "UNKNOWN"},
                "diagnostics": {"ping_status": "NOT_RUN", "failure_reason": f"PASSIVE_{self.event_kind}", "details": preview[:300], "root_cause_analysis": {"source_ip": source_ip, "trusted_source": True}},
                "impact_level": device.criticality if device else "LOW",
            })
        # A trap/syslog event is a prompt for active confirmation, not proof of
        # an outage. This keeps passive monitoring useful without alert spoofing.
        if device:
            from .monitor import poll_device
            asyncio.create_task(poll_device(device.id))


async def start_passive_listeners() -> list[asyncio.DatagramTransport]:
    loop = asyncio.get_running_loop()
    settings = get_settings()
    receivers = []
    for kind, port in (("SYSLOG", settings.syslog_port), ("SNMP_TRAP", settings.snmp_trap_port)):
        try:
            transport, _ = await loop.create_datagram_endpoint(lambda: PassiveProtocol(kind), local_addr=("0.0.0.0", port))
            receivers.append(transport)
            log.info("%s receiver listening on UDP %s", kind, port)
        except OSError as exc:
            log.warning("%s receiver unavailable on UDP %s: %s", kind, port, exc)
    return receivers
