"""
Alert Escalation Service for OIC NetRadar

Implements Section 6.2: Multi-Level Escalation Matrix
- Level 1: Immediate alert to Network Agent
- Level 2: Escalate to IT Supervisor if unacknowledged after 1 hour
- Level 3: Escalate to IT Manager if still unacknowledged
- Level 4: Escalate to Head of IT if still unacknowledged (optional)
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.models import Ticket, Device, Agent, DeviceStatusLog
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class AlertEscalationService:
    """
    Manages multi-level alert escalation.
    
    Escalation Levels:
    1. Network Agent (immediate)
    2. IT Supervisor (after 1 hour unacknowledged)
    3. IT Manager (after 2 hours unacknowledged)
    4. Head of IT (after 4 hours unacknowledged) - optional
    """
    
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.notification_service = NotificationService()
        
        # Escalation time thresholds (minutes)
        self.escalation_thresholds = {
            1: 60,    # Level 1 -> Level 2 after 60 min
            2: 120,   # Level 2 -> Level 3 after 120 min
            3: 240,   # Level 3 -> Level 4 after 240 min (optional)
        }
        
        # Escalation task
        self.escalation_task = None
        self.is_running = False
        
        # Track escalation notifications sent
        self.escalation_sent = set()
        
    async def start(self):
        """Start the escalation monitoring service."""
        self.is_running = True
        self.escalation_task = asyncio.create_task(self._escalation_loop())
        logger.info("✅ Alert escalation service started")
        
    async def stop(self):
        """Stop the escalation monitoring service."""
        self.is_running = False
        if self.escalation_task:
            self.escalation_task.cancel()
            try:
                await self.escalation_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Alert escalation service stopped")
    
    async def _escalation_loop(self):
        """Main escalation monitoring loop."""
        logger.info("🔄 Escalation loop started (checking every 60s)")
        
        while self.is_running:
            try:
                await self._check_escalations()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Escalation loop error: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    async def _check_escalations(self):
        """Check for tickets that need escalation."""
        async with self.db_session_factory() as session:
            # Get all open tickets
            result = await session.execute(
                select(Ticket).where(
                    Ticket.status.in_(["OPEN", "ACKNOWLEDGED"])
                )
            )
            tickets = result.scalars().all()
            
            if not tickets:
                return
            
            logger.debug(f"📋 Checking {len(tickets)} tickets for escalation")
            
            for ticket in tickets:
                await self._process_ticket(ticket, session)
            
            await session.commit()

    @staticmethod
    def _to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
        """
        Normalize a datetime to naive UTC.

        Values coming back from PostgreSQL TIMESTAMPTZ columns are
        timezone-aware, while `datetime.utcnow()` is naive. Subtracting
        one from the other raises `TypeError: can't subtract
        offset-naive and offset-aware datetimes`. This helper makes sure
        we always compare naive UTC datetimes.
        """
        if value is None:
            return None

        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        return value

    async def _process_ticket(self, ticket: Ticket, session: AsyncSession):
        """Process a single ticket for escalation."""
        current_time = datetime.utcnow()
        opened_at = self._to_naive_utc(ticket.opened_at)
        acknowledged_at = self._to_naive_utc(ticket.acknowledged_at)
        
        if not opened_at:
            return
        
        # If ticket is acknowledged, check if it needs re-escalation
        if ticket.status == "ACKNOWLEDGED" and acknowledged_at:
            # If acknowledged but not resolved after 2 hours, re-escalate
            elapsed_since_ack = (current_time - acknowledged_at).total_seconds() / 60
            if elapsed_since_ack >= 120:  # 2 hours
                logger.warning(f"⚠️ Ticket {ticket.id} acknowledged but not resolved for 2 hours")
                # Re-escalate to next level
                current_level = ticket.escalation_level
                if current_level < 3:
                    await self._escalate_ticket(ticket, current_level + 1, session)
            return
        
        # Only process OPEN tickets for escalation
        if ticket.status != "OPEN":
            return
        
        # Calculate how long the ticket has been open
        elapsed_minutes = (current_time - opened_at).total_seconds() / 60
        current_level = ticket.escalation_level
        
        # Check if escalation is needed
        if current_level == 1 and elapsed_minutes >= self.escalation_thresholds[1]:
            await self._escalate_ticket(ticket, 2, session)
            
        elif current_level == 2 and elapsed_minutes >= self.escalation_thresholds[2]:
            await self._escalate_ticket(ticket, 3, session)
            
        elif current_level == 3 and elapsed_minutes >= self.escalation_thresholds.get(3, 240):
            await self._escalate_ticket(ticket, 4, session)
    
    async def _escalate_ticket(
        self, 
        ticket: Ticket, 
        new_level: int, 
        session: AsyncSession
    ):
        """
        Escalate a ticket to a higher level.
        
        Args:
            ticket: Ticket to escalate
            new_level: New escalation level (2, 3, or 4)
            session: Database session
        """
        # Prevent duplicate escalation
        ticket_key = f"{ticket.id}_{new_level}"
        if ticket_key in self.escalation_sent:
            return
        self.escalation_sent.add(ticket_key)
        
        logger.warning(f"⚠️ Escalating ticket {ticket.id} from Level {ticket.escalation_level} to Level {new_level}")
        
        # Get device info
        device_result = await session.execute(
            select(Device).where(Device.id == ticket.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        if not device:
            logger.error(f"❌ Device not found for ticket {ticket.id}")
            return
        
        # Get device branch info
        branch_name = "Unknown"
        if device.branch_id:
            from app.models import Branch
            branch_result = await session.execute(
                select(Branch).where(Branch.id == device.branch_id)
            )
            branch = branch_result.scalar_one_or_none()
            if branch:
                branch_name = branch.name
        
        # Get appropriate agent for new level
        agent = await self._get_agent_for_level(new_level, session)
        
        # Update ticket
        old_level = ticket.escalation_level
        ticket.escalation_level = new_level
        if agent:
            ticket.assigned_agent_id = agent.id
        
        # Get diagnostic information
        diagnostic = await self._get_ticket_diagnostic(ticket.id, session)
        
        if diagnostic:
            # Build device info
            device_info = {
                "hostname": device.hostname,
                "ip_address": device.ip_address,
                "branch_name": branch_name,
                "branch_id": str(device.branch_id) if device.branch_id else None
            }
            
            # Get agent info for level 2 escalation notification
            agent_name = None
            agent_phone = None
            if new_level == 2:
                # Get original agent for level 2 notification
                orig_agent = await self._get_agent_for_level(1, session)
                if orig_agent:
                    agent_name = orig_agent.full_name
                    agent_phone = orig_agent.phone_number
            
            # Build message based on escalation level
            messages = self.notification_service.build_alert_message(
                device_info,
                diagnostic,
                str(ticket.id),
                level=new_level,
                agent_name=agent_name,
                agent_phone=agent_phone
            )
            
            # Send notifications
            notification_sent = False
            
            # Send to assigned agent
            if agent:
                # Email
                if agent.email and messages.get("email_body"):
                    email_result = await self.notification_service.send_email(
                        agent.email,
                        messages.get("email_subject", f"⚠️ NetRadar Escalation - Level {new_level}"),
                        messages.get("email_body", ""),
                        messages.get("email_html"),
                        str(ticket.id)
                    )
                    if email_result.get("success"):
                        notification_sent = True
                        logger.info(f"📧 Escalation email sent to {agent.email} (Level {new_level})")
                
                # SMS (only for Level 2 and above, or critical)
                if agent.phone_number and messages.get("sms"):
                    sms_result = await self.notification_service.send_sms(
                        agent.phone_number,
                        messages.get("sms", ""),
                        str(ticket.id)
                    )
                    if sms_result.get("success"):
                        notification_sent = True
                        logger.info(f"📱 Escalation SMS sent to {agent.phone_number} (Level {new_level})")
            
            # Send WebSocket update for frontend
            await self._broadcast_escalation(
                ticket, device, new_level, old_level, session
            )
        
        await session.flush()
        logger.info(f"✅ Ticket {ticket.id} escalated from Level {old_level} to Level {new_level}")
    
    async def _broadcast_escalation(
        self, 
        ticket: Ticket, 
        device: Device, 
        new_level: int, 
        old_level: int,
        session: AsyncSession
    ):
        """Broadcast escalation event via WebSocket."""
        try:
            from app.services.websocket_manager import websocket_manager
            
            if websocket_manager and websocket_manager.active_connections:
                await websocket_manager.broadcast({
                    "type": "ESCALATION",
                    "ticket_id": str(ticket.id),
                    "device_id": str(device.id),
                    "hostname": device.hostname,
                    "ip_address": device.ip_address,
                    "old_level": old_level,
                    "new_level": new_level,
                    "severity": ticket.severity,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
                logger.debug(f"📡 Escalation broadcasted to WebSocket clients")
        except Exception as e:
            logger.error(f"❌ Failed to broadcast escalation: {e}")
    
    async def _get_agent_for_level(self, level: int, session: AsyncSession) -> Optional[Agent]:
        """
        Get the appropriate agent for an escalation level.
        
        Level 1: Network Agent
        Level 2: Supervisor
        Level 3: Manager
        Level 4: Head of IT
        """
        role_map = {
            1: "NETWORK_AGENT",
            2: "SUPERVISOR",
            3: "MANAGER",
            4: "HEAD_OF_IT"
        }
        
        role = role_map.get(level)
        if not role:
            return None
        
        result = await session.execute(
            select(Agent).where(
                Agent.role == role,
                Agent.is_active == True
            )
        )
        agent = result.scalar_one_or_none()
        
        # Fallback: if no agent of this role, get next available
        if not agent:
            # Try to get any agent with higher role
            for r in role_map.values():
                if r == role:
                    continue
                result = await session.execute(
                    select(Agent).where(
                        Agent.role == r,
                        Agent.is_active == True
                    )
                )
                agent = result.scalar_one_or_none()
                if agent:
                    break
        
        # Last resort: get any active agent
        if not agent:
            result = await session.execute(
                select(Agent).where(Agent.is_active == True).limit(1)
            )
            agent = result.scalar_one_or_none()
        
        return agent
    
    async def _get_ticket_diagnostic(self, ticket_id: str, session: AsyncSession) -> Optional[Dict]:
        """
        Get the diagnostic information for a ticket.
        """
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        
        if not ticket:
            return None
        
        # Get latest status log for the device
        log_result = await session.execute(
            select(DeviceStatusLog).where(
                DeviceStatusLog.device_id == ticket.device_id
            ).order_by(DeviceStatusLog.recorded_at.desc()).limit(1)
        )
        log = log_result.scalar_one_or_none()
        
        if log and log.diagnostics:
            return log.diagnostics
        
        # Fallback: return basic diagnostic
        return {
            "event_type": "DEVICE_STATUS_CHANGE",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "device_info": {
                "status": "DOWN",
                "criticality_level": ticket.severity
            },
            "diagnostics": {
                "ping_status": "FAILED",
                "failure_reason": "UNKNOWN",
                "details": "No diagnostic data available",
                "root_cause_analysis": {}
            },
            "impact_level": ticket.severity
        }
    
    async def acknowledge_ticket(self, ticket_id: str, agent_id: str) -> bool:
        """
        Acknowledge a ticket (stops escalation).
        
        Args:
            ticket_id: ID of the ticket
            agent_id: ID of the agent acknowledging
            
        Returns:
            True if successful
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
            
            if not ticket:
                logger.error(f"❌ Ticket {ticket_id} not found")
                return False
            
            if ticket.status != "OPEN":
                logger.warning(f"⚠️ Ticket {ticket_id} already {ticket.status}")
                return False
            
            ticket.status = "ACKNOWLEDGED"
            ticket.acknowledged_at = datetime.utcnow()
            ticket.assigned_agent_id = agent_id
            
            # Clear escalation tracking
            self.escalation_sent.discard(f"{ticket_id}_2")
            self.escalation_sent.discard(f"{ticket_id}_3")
            
            await session.commit()
            logger.info(f"✅ Ticket {ticket_id} acknowledged by {agent_id}")
            
            # Broadcast acknowledgment
            await self._broadcast_acknowledgment(ticket_id, agent_id)
            
            return True
    
    async def _broadcast_acknowledgment(self, ticket_id: str, agent_id: str):
        """Broadcast acknowledgment event via WebSocket."""
        try:
            from app.services.websocket_manager import websocket_manager
            
            if websocket_manager and websocket_manager.active_connections:
                await websocket_manager.broadcast({
                    "type": "TICKET_ACKNOWLEDGED",
                    "ticket_id": ticket_id,
                    "agent_id": agent_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
        except Exception as e:
            logger.error(f"❌ Failed to broadcast acknowledgment: {e}")
    
    async def resolve_ticket(self, ticket_id: str) -> bool:
        """
        Resolve a ticket.
        
        Args:
            ticket_id: ID of the ticket
            
        Returns:
            True if successful
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
            
            if not ticket:
                logger.error(f"❌ Ticket {ticket_id} not found")
                return False
            
            ticket.status = "RESOLVED"
            ticket.resolved_at = datetime.utcnow()
            
            # Clear escalation tracking
            self.escalation_sent.discard(f"{ticket_id}_2")
            self.escalation_sent.discard(f"{ticket_id}_3")
            self.escalation_sent.discard(f"{ticket_id}_4")
            
            await session.commit()
            logger.info(f"✅ Ticket {ticket_id} resolved")
            
            # Broadcast resolution
            await self._broadcast_resolution(ticket_id)
            
            return True
    
    async def _broadcast_resolution(self, ticket_id: str):
        """Broadcast resolution event via WebSocket."""
        try:
            from app.services.websocket_manager import websocket_manager
            
            if websocket_manager and websocket_manager.active_connections:
                await websocket_manager.broadcast({
                    "type": "TICKET_RESOLVED",
                    "ticket_id": ticket_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
        except Exception as e:
            logger.error(f"❌ Failed to broadcast resolution: {e}")
    
    async def get_escalation_status(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get escalation status for a ticket.
        
        Args:
            ticket_id: ID of the ticket
            
        Returns:
            Dict with escalation status
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
            
            if not ticket:
                return {"error": "Ticket not found"}
            
            current_time = datetime.utcnow()
            opened_at = self._to_naive_utc(ticket.opened_at)
            acknowledged_at = self._to_naive_utc(ticket.acknowledged_at)
            
            elapsed_minutes = 0
            if opened_at:
                elapsed_minutes = (current_time - opened_at).total_seconds() / 60
            
            next_escalation = None
            if ticket.status == "OPEN":
                next_level = ticket.escalation_level + 1
                if next_level in self.escalation_thresholds:
                    threshold = self.escalation_thresholds[next_level]
                    remaining = max(0, threshold - elapsed_minutes)
                    next_escalation = {
                        "level": next_level,
                        "minutes_remaining": int(remaining),
                        "threshold_minutes": threshold
                    }
            
            return {
                "ticket_id": str(ticket.id),
                "current_level": ticket.escalation_level,
                "status": ticket.status,
                "elapsed_minutes": int(elapsed_minutes),
                "next_escalation": next_escalation,
                "assigned_agent_id": str(ticket.assigned_agent_id) if ticket.assigned_agent_id else None
            }