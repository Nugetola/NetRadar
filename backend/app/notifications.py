"""Notification delivery and escalation policy; credentials are environment-only."""
import asyncio
import json
import smtplib
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from sqlalchemy import select
from .config import get_settings
from .database import SessionLocal
from .models import Agent, Device, NotificationLog, Ticket


def _message(device: Device, ticket: Ticket, action: str) -> str:
    return (f"NetRadar alert\n\nSeverity: {ticket.severity}\nLocation: branch {device.branch_id or 'unassigned'}\n"
            f"Root Cause: {action}\nAction Required: Acknowledge and investigate ticket {ticket.id}.\n\n"
            f"Device: {device.hostname} ({device.ip_address})\nDashboard: {get_settings().dashboard_url}")


async def _audit(channel: str, outcome: str, payload: dict) -> None:
    async with SessionLocal() as session:
        session.add(NotificationLog(channel=channel, outcome=outcome, payload=payload))
        await session.commit()


async def send_email(recipient: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        await _audit("EMAIL", "SKIPPED_NOT_CONFIGURED", {"to": recipient, "subject": subject})
        return False
    def deliver():
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = settings.smtp_from, recipient, subject
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    try:
        await asyncio.to_thread(deliver)
        await _audit("EMAIL", "SENT", {"to": recipient, "subject": subject})
        return True
    except (OSError, smtplib.SMTPException) as exc:
        await _audit("EMAIL", "FAILED", {"to": recipient, "subject": subject, "error": str(exc)})
        return False


async def send_sms(phone_number: str, message: str) -> bool:
    settings = get_settings()
    if not settings.sms_gateway_url:
        await _audit("SMS", "SKIPPED_NOT_CONFIGURED", {"to": phone_number, "message": message})
        return False
    headers = {"Content-Type": "application/json"}
    if settings.sms_api_key:
        headers["Authorization"] = f"Bearer {settings.sms_api_key}"
    def deliver() -> int:
        request = urllib.request.Request(
            settings.sms_gateway_url,
            data=json.dumps({"to": phone_number, "message": message}).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    for attempt in range(1, 4):
        try:
            status = await asyncio.to_thread(deliver)
            if 200 <= status < 300:
                await _audit("SMS", "SENT", {"to": phone_number, "attempt": attempt})
                return True
        except (OSError, urllib.error.URLError) as exc:
            error = str(exc)
        else:
            error = f"HTTP {status}"
        if attempt < 3:
            await asyncio.sleep(attempt)
    await _audit("SMS", "FAILED", {"to": phone_number, "error": error, "attempts": 3})
    return False


async def _agent_for(session, device: Device, roles: tuple[str, ...]) -> Agent | None:
    # A branch-specific assignment wins; a null-branch agent is the global fallback.
    agents = list((await session.scalars(select(Agent).where(Agent.role.in_(roles), Agent.is_active.is_(True)))).all())
    return next((a for a in agents if a.branch_id == device.branch_id), None) or next((a for a in agents if a.branch_id is None), None)


async def open_ticket_and_notify(device_id: str, diagnostics: dict) -> None:
    """Create one open ticket per device and issue the Level 1 notification."""
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        if not device:
            return
        existing = await session.scalar(select(Ticket).where(Ticket.device_id == device.id, Ticket.status.in_(("OPEN", "ACKNOWLEDGED"))))
        if existing:
            return
        ticket = Ticket(device_id=device.id, severity=device.criticality, status="OPEN")
        agent = await _agent_for(session, device, ("NETWORK_AGENT",))
        if agent:
            ticket.assigned_agent_id = agent.id
        session.add(ticket); await session.commit(); await session.refresh(ticket)
        reason = diagnostics.get("failure_reason") or "Reachability failure"
        body = _message(device, ticket, reason)
        email_ok = await send_email(agent.email, f"[NetRadar L1] {device.hostname} is DOWN", body) if agent and agent.email else False
        sms_ok = False
        # Redundancy: HIGH-criticality incidents always page by SMS; any other
        # incident also falls back to SMS if the email channel failed, so a
        # critical alert is never silently lost to an SMTP outage.
        should_sms = device.criticality == "HIGH" or not email_ok
        if should_sms and agent and agent.phone_number:
            sms_ok = await send_sms(agent.phone_number, f"NetRadar {device.hostname} {device.ip_address}: {reason}. Ticket {ticket.id}. {get_settings().dashboard_url}")
        ticket.sms_sent, ticket.sms_sent_at = sms_ok, datetime.utcnow() if sms_ok else None
        await session.commit()
        from .integrations import create_external_ticket
        await create_external_ticket({"ticket_id": ticket.id, "device_id": device.id, "hostname": device.hostname, "ip_address": device.ip_address, "severity": ticket.severity, "tag": "Auto-generated by NetRadar", "failure_reason": reason})


async def escalate_unacknowledged() -> None:
    """Escalate Level 1 tickets that remain unacknowledged after the configured window."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=get_settings().level_2_escalation_minutes)
    async with SessionLocal() as session:
        tickets = list((await session.scalars(select(Ticket).where(Ticket.status == "OPEN", Ticket.escalation_level == 1, Ticket.opened_at <= cutoff))).all())
        for ticket in tickets:
            device = await session.get(Device, ticket.device_id)
            supervisor = await _agent_for(session, device, ("SUPERVISOR", "MANAGER")) if device else None
            if supervisor and supervisor.email:
                await send_email(supervisor.email, f"[NetRadar L2] Unacknowledged incident {ticket.id}", _message(device, ticket, "Level 1 was not acknowledged within the escalation window."))
            ticket.escalation_level = 2
        await session.commit()