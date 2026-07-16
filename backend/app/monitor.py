import asyncio
from datetime import datetime, timezone
from sqlalchemy import func, select
from .config import get_settings
from .database import SessionLocal
from .diagnostics import run_diagnostics
from .models import Branch, Device, DeviceStatusLog
from .realtime import manager
from .notifications import open_ticket_and_notify

CONFIRM_FAILURES = 2  # polling interval determines the confirmation window


async def poll_device(device_id: str):
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        if not device or not device.is_active:
            return
        # A parent switch outage explains children being unreachable. Suppress
        # their alerts/tickets; the parent carries the segment incident.
        if device.parent_switch_id:
            parent = await session.get(Device, device.parent_switch_id)
            if parent and parent.current_status == "DOWN":
                device.current_status = "DOWN"
                session.add(DeviceStatusLog(device_id=device.id, status="DOWN", failure_reason="DEPENDENCY_OUTAGE", diagnostics={"parent_switch_id": parent.id, "parent_hostname": parent.hostname}))
                await session.commit()
                return
        gateway_ip = None
        if device.branch_id:
            branch = await session.get(Branch, device.branch_id)
            gateway_ip = branch.wan_gateway_ip if branch else None
        switch_ip = None
        if device.parent_switch_id:
            switch = await session.get(Device, device.parent_switch_id)
            switch_ip = switch.ip_address if switch else None
        settings = get_settings()
        # Production: resolve VlanProfile.snmp_credential_ref via the secrets manager.
        # Dev/lab only: fall back to the community string configured in .env.
        snmp_community = settings.snmp_dev_community or None
        diagnostic = await run_diagnostics(
            device.ip_address, gateway_ip,
            switch_ip=switch_ip, switch_port_ifindex=device.switch_port_ifindex,
            snmp_community=snmp_community,
            dns_check_hostname=settings.dns_test_hostname if device.is_dns_server else None,
        )
        is_up = diagnostic["ping_status"] == "SUCCESS" or diagnostic["failure_reason"] == "ICMP_BLOCKED"
        if is_up:
            status, device.failure_count = "UP", 0
        else:
            device.failure_count += 1
            status = "DOWN" if device.failure_count >= CONFIRM_FAILURES else "UNSTABLE"
        changed = device.current_status != status
        device.current_status = status
        if status == "DOWN" and device.device_type in {"SWITCH", "ROUTER"}:
            dependent_count = await session.scalar(select(func.count(Device.id)).where(Device.parent_switch_id == device.id, Device.is_active.is_(True)))
            if dependent_count:
                diagnostic["failure_reason"] = "NETWORK_SEGMENT_DOWN"
                diagnostic["details"] = f"{device.device_type.title()} is unreachable; {dependent_count} downstream active device(s) are dependency-suppressed."
                diagnostic["root_cause_analysis"]["affected_downstream_devices"] = dependent_count
        session.add(DeviceStatusLog(device_id=device.id, status=status, failure_reason=diagnostic["failure_reason"], diagnostics=diagnostic))
        await session.commit()
        if status == "DOWN" and changed:
            await open_ticket_and_notify(device.id, diagnostic)
        if changed or status != "UP":
            await manager.broadcast({
                "event_type": "DEVICE_STATUS_CHANGE", "timestamp": datetime.now(timezone.utc).isoformat(),
                "device_info": {"id": device.id, "ip_address": device.ip_address, "hostname": device.hostname, "status": status, "criticality_level": device.criticality},
                "diagnostics": diagnostic, "impact_level": "CRITICAL" if device.criticality == "HIGH" and status == "DOWN" else device.criticality,
            })


async def poll_all_devices():
    async with SessionLocal() as session:
        ids = list((await session.scalars(select(Device.id).where(Device.is_active.is_(True)))).all())
    await asyncio.gather(*(poll_device(id_) for id_ in ids), return_exceptions=True)