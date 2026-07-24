# app/services/alert_service.py
"""
Alert Service for OIC NetRadar
Generates comprehensive alerts with full device and organization info
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional

from app.models import Device, Branch, HeadOfficeDirectorate


class AlertService:
    """Service for creating and managing alerts"""
    
    @staticmethod
    async def create_alert(device: Device, session: AsyncSession) -> Dict[str, Any]:
        """
        Create comprehensive alert with full device info
        
        Args:
            device: Device object
            session: Database session
        
        Returns:
            Dict with complete alert information
        """
        
        # Get organization info
        org_name = None
        org_type = None
        region = None
        
        if device.branch_id:
            branch_result = await session.execute(
                select(Branch).where(Branch.id == device.branch_id)
            )
            branch = branch_result.scalar_one_or_none()
            if branch:
                org_name = branch.name
                org_type = "Branch"
                region = branch.region
        elif device.directorate_id:
            dir_result = await session.execute(
                select(HeadOfficeDirectorate).where(HeadOfficeDirectorate.id == device.directorate_id)
            )
            directorate = dir_result.scalar_one_or_none()
            if directorate:
                org_name = directorate.name
                org_type = "Directorate/Office"
                region = "Addis Ababa"  # All directorates are in Head Office
        
        # Determine status details
        status = device.current_status or "UNKNOWN"
        
        if status in ["DOWN", "CRITICAL", "OFFLINE"]:
            severity = "HIGH"
            problem = f"Device is {status}"
            cause = "Network connectivity lost or device powered off"
            solutions = [
                "Check device connectivity",
                "Verify power status",
                "Check network cable",
                "Ping device to verify",
                "Check switch port status"
            ]
        elif status == "WARNING":
            severity = "MEDIUM"
            problem = "Device is UNSTABLE"
            cause = "Intermittent connectivity or high latency"
            solutions = [
                "Check network congestion",
                "Verify switch port status",
                "Monitor device logs",
                "Check bandwidth usage"
            ]
        elif status == "ONLINE":
            severity = "LOW"
            problem = "Device is ONLINE"
            cause = "Device operating normally"
            solutions = [
                "Monitor device health",
                "Regular maintenance checks"
            ]
        else:
            severity = "LOW"
            problem = f"Device status {status}"
            cause = "Diagnostic engine analyzing..."
            solutions = [
                "Run device diagnostics",
                "Check network connectivity",
                "Verify SNMP Agent status",
                "Check firewall and UDP port 161"
            ]
        
        return {
            # Alert Info
            "severity": severity,
            "status": status,
            "problem": problem,
            "cause": cause,
            "solutions": solutions,
            "timestamp": datetime.utcnow().isoformat(),
            
            # Device Info
            "device": {
                "id": str(device.id),
                "hostname": device.hostname,
                "ip_address": device.ip_address,
                "device_type": device.device_type,
                "criticality": device.criticality,
                "vlan_id": device.vlan_id,
                "subnet": device.subnet,
                "last_check": datetime.utcnow().isoformat()
            },
            
            # Organization Info
            "organization": {
                "name": org_name or "—",
                "type": org_type or "—",
                "region": region or "—"
            },
            
            # Additional Info
            "additional_info": {
                "parent_switch": str(device.parent_switch_id) if device.parent_switch_id else "—",
                "is_active": device.is_active,
                "failure_count": device.failure_count or 0,
                "uptime": "Unknown",
                "last_restart": None
            }
        }
    
    @staticmethod
    async def get_device_with_org(device_id: str, session: AsyncSession) -> Dict[str, Any]:
        """
        Get device with full organization info (without creating alert)
        
        Args:
            device_id: Device ID
            session: Database session
        
        Returns:
            Dict with device and organization info
        """
        result = await session.execute(
            select(Device).where(Device.id == device_id)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            return {"error": "Device not found"}
        
        return await AlertService.create_alert(device, session)


# ============================================================
# Function-based version for simple use
# ============================================================

async def create_alert(device: Device, session: AsyncSession) -> Dict[str, Any]:
    """Simple function wrapper for AlertService"""
    return await AlertService.create_alert(device, session)


async def get_device_alert(device_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Get device alert data without creating ticket"""
    return await AlertService.get_device_with_org(device_id, session)