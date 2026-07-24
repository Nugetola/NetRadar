import asyncio
import logging

from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.services.diagnostic_engine import DiagnosticEngine
from app.services.snmp_service import SNMPService
from app.services.websocket_manager import WebSocketManager
from app.services.alert_service import create_alert  # ✅ NEW

from app.models import (
    Device,
    DeviceStatusLog,
    Ticket,
    Agent,
)

logger = logging.getLogger(__name__)


class PollingService:
    """
    OIC NetRadar Polling Service.

    Features:
    - Concurrent device polling
    - SNMP polling
    - Ping and network diagnostics
    - Debounce window
    - Flapping protection
    - Automatic ticket creation with full alert data
    - Ticket recovery/resolution
    - WebSocket notifications
    - SMS notification placeholder
    - Email notification placeholder
    """

    def __init__(
        self,
        db_session_factory,
        websocket_manager: Optional[WebSocketManager] = None,
        diagnostic_engine: Optional[DiagnosticEngine] = None,
        snmp_service: Optional[SNMPService] = None,
        poll_interval: int = 60,
        debounce_window: int = 180,
        snmp_community: str = "public",
    ):
        self.db_session_factory = db_session_factory
        self.websocket_manager = websocket_manager
        self.diagnostic_engine = diagnostic_engine or DiagnosticEngine()
        self.snmp_service = snmp_service or SNMPService(community=snmp_community)
        self.poll_interval = poll_interval
        self.debounce_window = debounce_window
        self.polling_task: Optional[asyncio.Task] = None
        self.is_running = False

        # -------------------------------------------------
        # DEVICE TRACKING
        # -------------------------------------------------
        self.device_failure_tracker: Dict[str, Dict[str, Any]] = {}
        self.alert_cooldown: Dict[str, datetime] = {}
        self.device_status_cache: Dict[str, str] = {}

    # =====================================================
    # START POLLING
    # =====================================================
    async def start_polling(self):
        if self.is_running:
            logger.warning("Polling service is already running")
            return

        self.is_running = True
        self.polling_task = asyncio.create_task(self._polling_loop())
        logger.info("✅ Polling service started")

    # =====================================================
    # STOP POLLING
    # =====================================================
    async def stop_polling(self):
        self.is_running = False

        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
            self.polling_task = None

        logger.info("🛑 Polling service stopped")

    # =====================================================
    # MAIN POLLING LOOP
    # =====================================================
    async def _polling_loop(self):
        logger.info(
            "🔄 Polling loop started "
            f"(interval: {self.poll_interval}s)"
        )

        while self.is_running:
            try:
                start_time = datetime.utcnow()

                await self._poll_all_devices()

                elapsed = (datetime.utcnow() - start_time).total_seconds()
                sleep_time = max(0, self.poll_interval - elapsed)

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break

            except Exception as exc:
                logger.error(
                    f"❌ Polling loop error: {exc}",
                    exc_info=True,
                )
                await asyncio.sleep(5)

    # =====================================================
    # POLL ALL DEVICES
    # =====================================================
    async def _poll_all_devices(self):
        try:
            async with self.db_session_factory() as session:
                result = await session.execute(
                    select(Device).where(Device.is_active == True)
                )
                devices = result.scalars().all()

                if not devices:
                    logger.warning("⚠️ No active devices found to poll")
                    return

                logger.info(f"📊 Polling {len(devices)} devices")

                semaphore = asyncio.Semaphore(50)

                async def poll_with_semaphore(device):
                    async with semaphore:
                        await self._poll_single_device(device, session)

                tasks = [poll_with_semaphore(device) for device in devices]

                await asyncio.gather(*tasks, return_exceptions=True)

                await session.commit()

        except Exception as exc:
            logger.error(
                f"❌ Error polling devices: {exc}",
                exc_info=True,
            )

    # =====================================================
    # POLL SINGLE DEVICE
    # =====================================================
    async def _poll_single_device(
        self,
        device: Device,
        session: AsyncSession,
    ):
        try:
            device_id = str(device.id)
            ip_address = str(device.ip_address)

            # -------------------------------------------------
            # SNMP POLLING
            # -------------------------------------------------
            logger.info(f"📡 SNMP polling {ip_address}")

            snmp_result = await self.snmp_service.get_system_info(ip_address)

            if snmp_result.get("success", False):
                logger.info(f"✅ SNMP poll successful for {ip_address}")
            else:
                logger.warning(
                    f"⚠️ SNMP poll failed for {ip_address}: "
                    f"{snmp_result.get('error')}"
                )

            # -------------------------------------------------
            # NETWORK DIAGNOSTICS
            # -------------------------------------------------
            diagnostic_result = await self.diagnostic_engine.run_diagnostics(
                ip_address
            )

            status = diagnostic_result.get("device_info", {}).get(
                "status", "UNKNOWN"
            )

            failure_reason = diagnostic_result.get("diagnostics", {}).get(
                "failure_reason", "NONE"
            )

            previous_status = self.device_status_cache.get(
                device_id, "UNKNOWN"
            )

            self.device_status_cache[device_id] = status

            await self._process_status_change(
                device,
                status,
                previous_status,
                failure_reason,
                diagnostic_result,
                session,
            )

        except Exception as exc:
            logger.error(
                f"❌ Error polling device {device.ip_address}: {exc}",
                exc_info=True,
            )

    # =====================================================
    # PROCESS STATUS
    # =====================================================
    async def _process_status_change(
        self,
        device: Device,
        status: str,
        previous_status: str,
        failure_reason: str,
        diagnostic: Dict[str, Any],
        session: AsyncSession,
    ):
        device_id = str(device.id)
        current_time = datetime.utcnow()

        # -------------------------------------------------
        # DEVICE UP
        # -------------------------------------------------
        if status == "UP":
            if device_id in self.device_failure_tracker:
                tracker = self.device_failure_tracker[device_id]

                if tracker.get("count", 0) > 0:
                    await self._handle_device_recovery(device, session)

                del self.device_failure_tracker[device_id]

            await self._log_status(
                device, status, failure_reason, diagnostic, session
            )
            return

        # -------------------------------------------------
        # DEVICE DOWN
        # -------------------------------------------------
        if device_id not in self.device_failure_tracker:
            self.device_failure_tracker[device_id] = {
                "count": 0,
                "first_failure": current_time,
                "last_failure": current_time,
                "diagnostic": diagnostic,
            }

        tracker = self.device_failure_tracker[device_id]
        tracker["count"] += 1
        tracker["last_failure"] = current_time
        tracker["diagnostic"] = diagnostic

        elapsed = (current_time - tracker["first_failure"]).total_seconds()

        if elapsed >= self.debounce_window:
            await self._handle_device_down(
                device, failure_reason, diagnostic, session
            )
            tracker["count"] = 0
            tracker["first_failure"] = current_time

        await self._log_status(
            device, status, failure_reason, diagnostic, session
        )

    # =====================================================
    # DEVICE DOWN - UPDATED WITH ALERT SERVICE
    # =====================================================
    async def _handle_device_down(
        self,
        device: Device,
        failure_reason: str,
        diagnostic: Dict[str, Any],
        session: AsyncSession,
    ):
        device_id = str(device.id)

        # Check for existing open ticket
        result = await session.execute(
            select(Ticket).where(
                Ticket.device_id == device.id,
                Ticket.status.in_(["OPEN", "ACKNOWLEDGED"]),
            )
        )

        existing_ticket = result.scalar_one_or_none()

        if existing_ticket:
            logger.info(
                f"ℹ️ Device {device.ip_address} already has open ticket "
                f"{existing_ticket.id}"
            )
            return

        # -------------------------------------------------
        # ALERT COOLDOWN
        # -------------------------------------------------
        if device_id in self.alert_cooldown:
            cooldown_time = self.alert_cooldown[device_id]
            elapsed = (datetime.utcnow() - cooldown_time).total_seconds()

            if elapsed < 3600:
                logger.info(
                    f"⏱️ Alert cooldown active for {device.ip_address}"
                )
                return

        # =========================================================
        # ✅ CREATE COMPREHENSIVE ALERT USING ALERT SERVICE
        # =========================================================
        alert_data = await create_alert(device, session)

        # Get severity from alert data
        severity = alert_data.get("severity", "MEDIUM")
        
        # Create ticket with alert data
        ticket = Ticket(
            device_id=device.id,
            severity=severity,
            status="OPEN",
            escalation_level=1,
        )

        session.add(ticket)
        await session.flush()

        # Assign agent
        agent = await self._get_agent_for_device(device, session)

        if agent:
            ticket.assigned_agent_id = agent.id

        # Send notifications with full alert data
        await self._send_notifications(
            device, alert_data, ticket, agent, session
        )

        self.alert_cooldown[device_id] = datetime.utcnow()

        # Broadcast via WebSocket with full alert data
        if self.websocket_manager:
            await self.websocket_manager.broadcast({
                "type": "DEVICE_DOWN",
                "alert": alert_data,  # ✅ Full alert data
                "device_id": device_id,
                "hostname": device.hostname,
                "ip_address": str(device.ip_address),
                "ticket_id": str(ticket.id),
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })

        logger.warning(
            f"🚨 Ticket {ticket.id} created for {device.ip_address} "
            f"(Severity: {severity})"
        )
        
        # Log alert summary
        logger.info(
            f"📋 Alert Details - Device: {alert_data['device']['hostname']}, "
            f"Org: {alert_data['organization']['name']}, "
            f"Region: {alert_data['organization']['region']}, "
            f"Problem: {alert_data['problem']}"
        )

    # =====================================================
    # DEVICE RECOVERY
    # =====================================================
    async def _handle_device_recovery(
        self,
        device: Device,
        session: AsyncSession,
    ):
        result = await session.execute(
            select(Ticket).where(
                Ticket.device_id == device.id,
                Ticket.status.in_(["OPEN", "ACKNOWLEDGED"]),
            )
        )

        open_tickets = result.scalars().all()

        for ticket in open_tickets:
            ticket.status = "RESOLVED"
            ticket.resolved_at = datetime.utcnow()

            logger.info(
                f"✅ Ticket {ticket.id} resolved for {device.ip_address}"
            )

        if self.websocket_manager:
            await self.websocket_manager.broadcast({
                "type": "DEVICE_UP",
                "device_id": str(device.id),
                "hostname": device.hostname,
                "ip_address": str(device.ip_address),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })

    # =====================================================
    # STATUS LOG
    # =====================================================
    async def _log_status(
        self,
        device: Device,
        status: str,
        failure_reason: str,
        diagnostic: Dict[str, Any],
        session: AsyncSession,
    ):
        status_log = DeviceStatusLog(
            device_id=device.id,
            status=status,
            failure_reason=failure_reason if status == "DOWN" else None,
            diagnostics=diagnostic,
        )

        session.add(status_log)

    # =====================================================
    # GET AGENT
    # =====================================================
    async def _get_agent_for_device(
        self,
        device: Device,
        session: AsyncSession,
    ) -> Optional[Agent]:
        if device.branch_id:
            result = await session.execute(
                select(Agent).where(Agent.role == "NETWORK_AGENT")
            )
            agent = result.scalar_one_or_none()

            if agent:
                return agent

        result = await session.execute(
            select(Agent).where(Agent.role == "SUPERVISOR")
        )
        agent = result.scalar_one_or_none()

        if agent:
            return agent

        result = await session.execute(select(Agent).limit(1))

        return result.scalar_one_or_none()

    # =====================================================
    # NOTIFICATIONS - UPDATED WITH ALERT DATA
    # =====================================================
    async def _send_notifications(
        self,
        device: Device,
        alert_data: Dict[str, Any],
        ticket: Ticket,
        agent: Optional[Agent],
        session: AsyncSession,
    ):
        if not agent:
            logger.warning(f"⚠️ No agent found for {device.ip_address}")
            return

        # Extract alert details
        problem = alert_data.get("problem", "Device issue detected")
        cause = alert_data.get("cause", "Unknown")
        solutions = alert_data.get("solutions", [])
        org = alert_data.get("organization", {})
        device_info = alert_data.get("device", {})

        message = (
            "🚨 NetRadar ALERT\n"
            "═" * 40 + "\n"
            f"Device: {device_info.get('hostname', device.hostname)}\n"
            f"IP: {device_info.get('ip_address', device.ip_address)}\n"
            f"Type: {device_info.get('device_type', 'Unknown')}\n"
            f"Criticality: {device_info.get('criticality', 'MEDIUM')}\n"
            f"Organization: {org.get('name', '—')} ({org.get('type', '—')})\n"
            f"Region: {org.get('region', '—')}\n"
            "═" * 40 + "\n"
            f"Status: {alert_data.get('status', 'UNKNOWN')}\n"
            f"Problem: {problem}\n"
            f"Cause: {cause}\n"
            "═" * 40 + "\n"
            f"Solutions:\n"
        )
        
        for i, solution in enumerate(solutions[:3], 1):
            message += f"  {i}. {solution}\n"
        
        message += (
            "═" * 40 + "\n"
            f"Ticket: {str(ticket.id)[:8]}\n"
            f"Severity: {ticket.severity}\n"
            f"Time: {datetime.utcnow().isoformat()}"
        )

        # -------------------------------------------------
        # SMS
        # -------------------------------------------------
        if agent.phone_number:
            try:
                sent = await self._send_sms(
                    agent.phone_number, message[:160]
                )

                if sent:
                    ticket.sms_sent = True
                    ticket.sms_sent_at = datetime.utcnow()

                    logger.info(f"📱 SMS sent to {agent.phone_number}")
                else:
                    logger.warning(
                        f"⚠️ SMS failed to {agent.phone_number}"
                    )

            except Exception as exc:
                logger.error(f"❌ SMS error: {exc}")

        # -------------------------------------------------
        # EMAIL
        # -------------------------------------------------
        if agent.email:
            try:
                await self._send_email(
                    agent.email, message, device, alert_data
                )

                logger.info(f"📧 Email sent to {agent.email}")

            except Exception as exc:
                logger.error(f"❌ Email error: {exc}")

    # =====================================================
    # SMS PLACEHOLDER
    # =====================================================
    async def _send_sms(
        self,
        phone_number: str,
        message: str,
    ) -> bool:
        logger.info(f"📱 [SMS] To: {phone_number}")
        logger.info(f"Message: {message[:100]}...")

        return True

    # =====================================================
    # EMAIL PLACEHOLDER - UPDATED
    # =====================================================
    async def _send_email(
        self,
        email: str,
        message: str,
        device: Device,
        alert_data: Dict[str, Any],
    ):
        org = alert_data.get("organization", {})
        
        subject = (
            f"[NetRadar] {alert_data.get('severity', 'ALERT')} - "
            f"{device.hostname} ({org.get('name', 'Unknown')})"
        )
        
        logger.info(f"📧 [Email] To: {email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Message: {message[:200]}...")

        return True

    # =====================================================
    # DEVICE COUNT
    # =====================================================
    async def get_device_count(self) -> int:
        try:
            async with self.db_session_factory() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(Device)
                    .where(Device.is_active == True)
                )

                return result.scalar() or 0

        except Exception as exc:
            logger.error(f"❌ Error getting device count: {exc}")
            return 0