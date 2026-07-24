"""
API Routes for OIC NetRadar

Provides REST endpoints for:
- Device management (CRUD)
- Branch management
- Directorate management
- Agent management
- Ticket management
- Status history
- Dashboard summary
- Reports
- Alerts
- Diagnostics
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func, text
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import uuid

from app.database import get_db
from app.models import Device, Branch, Agent, Ticket, DeviceStatusLog, HeadOfficeDirectorate
from app.services.diagnostic_engine import DiagnosticEngine
from app.services.websocket_manager import websocket_manager

# ============================================================================
# Pydantic Schemas
# ============================================================================

class DeviceCreate(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=100)
    ip_address: str = Field(..., pattern=r'^(\d{1,3}\.){3}\d{1,3}$')
    branch_id: Optional[str] = None
    directorate_id: Optional[str] = None
    device_type: Optional[str] = Field(None, max_length=30)
    criticality: str = Field("MEDIUM", pattern=r'^(HIGH|MEDIUM|LOW)$')
    parent_switch_id: Optional[str] = None
    vlan_id: Optional[int] = Field(None, ge=1, le=4094)
    subnet: Optional[str] = Field(None, pattern=r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$')

class DeviceUpdate(BaseModel):
    hostname: Optional[str] = Field(None, min_length=1, max_length=100)
    ip_address: Optional[str] = Field(None, pattern=r'^(\d{1,3}\.){3}\d{1,3}$')
    branch_id: Optional[str] = None
    directorate_id: Optional[str] = None
    device_type: Optional[str] = Field(None, max_length=30)
    criticality: Optional[str] = Field(None, pattern=r'^(HIGH|MEDIUM|LOW)$')
    parent_switch_id: Optional[str] = None
    is_active: Optional[bool] = None
    vlan_id: Optional[int] = Field(None, ge=1, le=4094)
    subnet: Optional[str] = Field(None, pattern=r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$')

class TicketCreate(BaseModel):
    device_id: str
    severity: str = Field(..., pattern=r'^(CRITICAL|HIGH|MEDIUM|LOW)$')
    assigned_agent_id: Optional[str] = None

class TicketUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern=r'^(OPEN|ACKNOWLEDGED|RESOLVED|CLOSED)$')
    escalation_level: Optional[int] = Field(None, ge=1, le=5)
    assigned_agent_id: Optional[str] = None

class AgentCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern=r'^(NETWORK_AGENT|SUPERVISOR|HELPDESK|MANAGER)$')
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    phone_number: str = Field(..., min_length=10, max_length=20)
    branch_id: Optional[str] = None
    directorate_id: Optional[str] = None
    is_active: bool = True

class AgentUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[str] = Field(None, pattern=r'^(NETWORK_AGENT|SUPERVISOR|HELPDESK|MANAGER)$')
    email: Optional[str] = Field(None, pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    phone_number: Optional[str] = Field(None, min_length=10, max_length=20)
    branch_id: Optional[str] = None
    directorate_id: Optional[str] = None
    is_active: Optional[bool] = None

class BranchCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    wan_gateway_ip: Optional[str] = Field(None, pattern=r'^(\d{1,3}\.){3}\d{1,3}$')

class DirectorateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=10)

class DirectorateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=10)

# ============================================================================
# Router
# ============================================================================

router = APIRouter(prefix="/api/v1", tags=["NetRadar API"])

# ============================================================================
# Health Check
# ============================================================================

@router.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"status": "pong", "timestamp": datetime.utcnow().isoformat() + "Z"}

# ============================================================================
# Device Endpoints - CRUD
# ============================================================================

@router.get("/devices")
async def get_devices(
    branch_id: Optional[str] = None,
    directorate_id: Optional[str] = None,
    device_type: Optional[str] = None,
    criticality: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db)
):
    """
    Get all devices with optional filtering.
    """
    query = select(Device).where(Device.is_active == True)

    if branch_id:
        query = query.where(Device.branch_id == branch_id)
    if directorate_id:
        query = query.where(Device.directorate_id == directorate_id)
    if device_type:
        query = query.where(Device.device_type == device_type)
    if criticality:
        query = query.where(Device.criticality == criticality)

    query = query.order_by(Device.hostname).offset(offset).limit(limit)

    result = await session.execute(query)
    devices = result.scalars().all()

    devices_data = []
    for device in devices:
        status_query = select(DeviceStatusLog).where(
            DeviceStatusLog.device_id == device.id
        ).order_by(desc(DeviceStatusLog.recorded_at)).limit(1)
        status_result = await session.execute(status_query)
        latest_status = status_result.scalar_one_or_none()

        # Get organization name
        org_name = None
        org_type = None
        if device.branch_id:
            branch_result = await session.execute(
                select(Branch.name).where(Branch.id == device.branch_id)
            )
            org_name = branch_result.scalar_one_or_none()
            org_type = "branch"
        elif device.directorate_id:
            dir_result = await session.execute(
                select(HeadOfficeDirectorate.name).where(HeadOfficeDirectorate.id == device.directorate_id)
            )
            org_name = dir_result.scalar_one_or_none()
            org_type = "directorate"

        devices_data.append({
            "id": str(device.id),
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "criticality": device.criticality,
            "branch_id": str(device.branch_id) if device.branch_id else None,
            "directorate_id": str(device.directorate_id) if device.directorate_id else None,
            "organization": org_name,
            "org_type": org_type,
            "vlan_id": device.vlan_id,
            "subnet": device.subnet,
            "parent_switch_id": str(device.parent_switch_id) if device.parent_switch_id else None,
            "status": latest_status.status if latest_status else "UNKNOWN",
            "last_check": latest_status.recorded_at.isoformat() if latest_status else None
        })

    return {
        "count": len(devices_data),
        "devices": devices_data
    }

@router.get("/devices/{device_id}")
async def get_device(
    device_id: str = Path(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed device information.
    """
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    status_query = select(DeviceStatusLog).where(
        DeviceStatusLog.device_id == device.id
    ).order_by(desc(DeviceStatusLog.recorded_at)).limit(1)
    status_result = await session.execute(status_query)
    latest_status = status_result.scalar_one_or_none()

    ticket_query = select(Ticket).where(
        Ticket.device_id == device.id,
        Ticket.status.in_(["OPEN", "ACKNOWLEDGED"])
    )
    ticket_result = await session.execute(ticket_query)
    open_tickets = ticket_result.scalars().all()

    # Get organization name
    org_name = None
    org_type = None
    if device.branch_id:
        branch_result = await session.execute(
            select(Branch.name).where(Branch.id == device.branch_id)
        )
        org_name = branch_result.scalar_one_or_none()
        org_type = "branch"
    elif device.directorate_id:
        dir_result = await session.execute(
            select(HeadOfficeDirectorate.name).where(HeadOfficeDirectorate.id == device.directorate_id)
        )
        org_name = dir_result.scalar_one_or_none()
        org_type = "directorate"

    return {
        "id": str(device.id),
        "hostname": device.hostname,
        "ip_address": device.ip_address,
        "device_type": device.device_type,
        "criticality": device.criticality,
        "branch_id": str(device.branch_id) if device.branch_id else None,
        "directorate_id": str(device.directorate_id) if device.directorate_id else None,
        "organization": org_name,
        "org_type": org_type,
        "vlan_id": device.vlan_id,
        "subnet": device.subnet,
        "parent_switch_id": str(device.parent_switch_id) if device.parent_switch_id else None,
        "is_active": device.is_active,
        "created_at": device.created_at.isoformat(),
        "status": latest_status.status if latest_status else "UNKNOWN",
        "last_check": latest_status.recorded_at.isoformat() if latest_status else None,
        "open_tickets": len(open_tickets),
        "tickets": [str(t.id) for t in open_tickets]
    }

@router.post("/devices")
async def create_device(
    device_data: DeviceCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new device.
    """
    # Check if IP already exists
    result = await session.execute(
        select(Device).where(Device.ip_address == device_data.ip_address)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Device with IP {device_data.ip_address} already exists")

    # Validate: Must have either branch_id OR directorate_id, not both
    if not device_data.branch_id and not device_data.directorate_id:
        raise HTTPException(status_code=400, detail="Device must belong to either a Branch or a Directorate")
    if device_data.branch_id and device_data.directorate_id:
        raise HTTPException(status_code=400, detail="Device cannot belong to both a Branch and a Directorate")

    device = Device(
        hostname=device_data.hostname,
        ip_address=device_data.ip_address,
        branch_id=device_data.branch_id,
        directorate_id=device_data.directorate_id,
        device_type=device_data.device_type,
        criticality=device_data.criticality,
        parent_switch_id=device_data.parent_switch_id,
        vlan_id=device_data.vlan_id,
        subnet=device_data.subnet,
        is_active=True
    )

    session.add(device)
    await session.commit()
    await session.refresh(device)

    # Create initial status log
    status_log = DeviceStatusLog(
        device_id=device.id,
        status="UNKNOWN",
        diagnostics={"message": "Device added to monitoring system"}
    )
    session.add(status_log)
    await session.commit()

    return {
        "message": "Device created successfully",
        "device": {
            "id": str(device.id),
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "criticality": device.criticality,
            "vlan_id": device.vlan_id,
            "branch_id": str(device.branch_id) if device.branch_id else None,
            "directorate_id": str(device.directorate_id) if device.directorate_id else None,
            "parent_switch_id": str(device.parent_switch_id) if device.parent_switch_id else None,
            "is_active": device.is_active,
            "created_at": device.created_at.isoformat()
        }
    }

@router.put("/devices/{device_id}")
async def update_device(
    device_id: str,
    device_data: DeviceUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update an existing device.
    """
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    update_data = device_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)

    await session.commit()
    await session.refresh(device)

    return {
        "message": "Device updated successfully",
        "device": {
            "id": str(device.id),
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "criticality": device.criticality,
            "vlan_id": device.vlan_id,
            "branch_id": str(device.branch_id) if device.branch_id else None,
            "directorate_id": str(device.directorate_id) if device.directorate_id else None,
            "parent_switch_id": str(device.parent_switch_id) if device.parent_switch_id else None,
            "is_active": device.is_active
        }
    }

@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Soft delete a device (set is_active=False).
    """
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.is_active = False
    await session.commit()

    return {"message": f"Device '{device.hostname}' deactivated successfully"}

# ============================================================================
# Device Status History Endpoints
# ============================================================================

@router.get("/devices/{device_id}/history")
async def get_device_history(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db)
):
    """
    Get status history for a device.
    """
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not found")

    query = select(DeviceStatusLog).where(
        DeviceStatusLog.device_id == device_id
    ).order_by(desc(DeviceStatusLog.recorded_at)).offset(offset).limit(limit)

    result = await session.execute(query)
    logs = result.scalars().all()

    return {
        "device_id": device_id,
        "count": len(logs),
        "history": [
            {
                "id": log.id,
                "status": log.status,
                "failure_reason": log.failure_reason,
                "diagnostics": log.diagnostics,
                "recorded_at": log.recorded_at.isoformat()
            }
            for log in logs
        ]
    }

@router.get("/devices/{device_id}/status")
async def get_device_status(
    device_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get current status of a device (with diagnostic details).
    """
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    query = select(DeviceStatusLog).where(
        DeviceStatusLog.device_id == device.id
    ).order_by(desc(DeviceStatusLog.recorded_at)).limit(1)

    result = await session.execute(query)
    latest = result.scalar_one_or_none()

    if not latest:
        return {
            "device_id": device_id,
            "status": "UNKNOWN",
            "last_check": None
        }

    return {
        "device_id": device_id,
        "hostname": device.hostname,
        "ip_address": device.ip_address,
        "status": latest.status,
        "failure_reason": latest.failure_reason,
        "diagnostics": latest.diagnostics,
        "last_check": latest.recorded_at.isoformat()
    }

# ============================================================================
# Diagnostic Endpoints
# ============================================================================

@router.post("/devices/{device_id}/diagnose")
async def diagnose_device(
    device_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Run on-demand diagnostics on a device.
    """
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    engine = DiagnosticEngine()
    diagnostic_result = await engine.run_diagnostics(device.ip_address)

    status_log = DeviceStatusLog(
        device_id=device.id,
        status=diagnostic_result.get("device_info", {}).get("status", "UNKNOWN"),
        failure_reason=diagnostic_result.get("diagnostics", {}).get("failure_reason"),
        diagnostics=diagnostic_result
    )
    session.add(status_log)
    await session.commit()

    return diagnostic_result

# ============================================================================
# Ticket Endpoints
# ============================================================================

@router.get("/tickets")
async def get_tickets(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    device_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db)
):
    """
    Get tickets with optional filtering.
    """
    query = select(Ticket)

    if status:
        query = query.where(Ticket.status == status)
    if severity:
        query = query.where(Ticket.severity == severity)
    if device_id:
        query = query.where(Ticket.device_id == device_id)
    if agent_id:
        query = query.where(Ticket.assigned_agent_id == agent_id)

    query = query.order_by(desc(Ticket.opened_at)).offset(offset).limit(limit)

    result = await session.execute(query)
    tickets = result.scalars().all()

    return {
        "count": len(tickets),
        "tickets": [
            {
                "id": str(t.id),
                "device_id": str(t.device_id),
                "severity": t.severity,
                "status": t.status,
                "escalation_level": t.escalation_level,
                "assigned_agent_id": str(t.assigned_agent_id) if t.assigned_agent_id else None,
                "sms_sent": t.sms_sent,
                "opened_at": t.opened_at.isoformat(),
                "acknowledged_at": t.acknowledged_at.isoformat() if t.acknowledged_at else None,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None
            }
            for t in tickets
        ]
    }

@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed ticket information.
    """
    result = await session.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    device_result = await session.execute(
        select(Device).where(Device.id == ticket.device_id)
    )
    device = device_result.scalar_one_or_none()

    return {
        "id": str(ticket.id),
        "device": {
            "id": str(device.id) if device else None,
            "hostname": device.hostname if device else "Unknown",
            "ip_address": device.ip_address if device else "Unknown"
        },
        "severity": ticket.severity,
        "status": ticket.status,
        "escalation_level": ticket.escalation_level,
        "assigned_agent_id": str(ticket.assigned_agent_id) if ticket.assigned_agent_id else None,
        "sms_sent": ticket.sms_sent,
        "sms_sent_at": ticket.sms_sent_at.isoformat() if ticket.sms_sent_at else None,
        "opened_at": ticket.opened_at.isoformat(),
        "acknowledged_at": ticket.acknowledged_at.isoformat() if ticket.acknowledged_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None
    }

@router.put("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    ticket_data: TicketUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update a ticket (acknowledge, resolve, escalate).
    """
    result = await session.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    update_data = ticket_data.dict(exclude_unset=True)

    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == "ACKNOWLEDGED" and ticket.status == "OPEN":
            ticket.acknowledged_at = datetime.utcnow()
        elif new_status == "RESOLVED" and ticket.status in ["OPEN", "ACKNOWLEDGED"]:
            ticket.resolved_at = datetime.utcnow()

    for key, value in update_data.items():
        setattr(ticket, key, value)

    await session.commit()
    await session.refresh(ticket)

    return {
        "message": "Ticket updated successfully",
        "ticket": {
            "id": str(ticket.id),
            "status": ticket.status,
            "escalation_level": ticket.escalation_level
        }
    }

# ============================================================================
# Alert Endpoints
# ============================================================================

@router.get("/alerts")
async def get_active_alerts(
    session: AsyncSession = Depends(get_db)
):
    """
    Get all active alerts (open tickets with device info).
    """
    result = await session.execute(
        select(Ticket)
        .where(Ticket.status.in_(["OPEN", "ACKNOWLEDGED"]))
        .order_by(desc(Ticket.opened_at))
    )
    tickets = result.scalars().all()

    alerts = []
    for ticket in tickets:
        device_result = await session.execute(
            select(Device).where(Device.id == ticket.device_id)
        )
        device = device_result.scalar_one_or_none()

        if not device:
            continue

        alerts.append({
            "id": str(ticket.id),
            "title": f"{ticket.severity} Network Alert",
            "severity": ticket.severity,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "problem": "Network or monitoring problem detected.",
            "cause": "Diagnostic engine is analyzing the device.",
            "solution": [
                "Run device diagnostics",
                "Check network connectivity",
                "Verify SNMP Agent status",
                "Check firewall and UDP port 161"
            ],
            "status": ticket.status,
            "created_at": ticket.opened_at.isoformat(),
            "escalation_level": ticket.escalation_level
        })

    return {
        "count": len(alerts),
        "alerts": alerts
    }

# ============================================================================
# Branch Endpoints
# ============================================================================

@router.get("/branches")
async def get_branches(
    session: AsyncSession = Depends(get_db)
):
    """
    Get all branches.
    """
    result = await session.execute(select(Branch).order_by(Branch.name))
    branches = result.scalars().all()

    branches_data = []
    for branch in branches:
        count_result = await session.execute(
            select(func.count()).select_from(Device).where(
                Device.branch_id == branch.id,
                Device.is_active == True
            )
        )
        device_count = count_result.scalar() or 0

        branches_data.append({
            "id": str(branch.id),
            "name": branch.name,
            "region": branch.region,
            "wan_gateway_ip": branch.wan_gateway_ip,
            "device_count": device_count
        })

    return {"branches": branches_data}

@router.post("/branches")
async def create_branch(
    branch_data: BranchCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new branch.
    """
    branch = Branch(
        name=branch_data.name,
        region=branch_data.region,
        wan_gateway_ip=branch_data.wan_gateway_ip
    )

    session.add(branch)
    await session.commit()
    await session.refresh(branch)

    return {
        "message": "Branch created successfully",
        "branch": {
            "id": str(branch.id),
            "name": branch.name
        }
    }

# ============================================================================
# DIRECTORATES ENDPOINTS (NEW)
# ============================================================================

@router.get("/directorates")
async def get_directorates(
    session: AsyncSession = Depends(get_db)
):
    """
    Get all Head Office Directorates.
    """
    result = await session.execute(
        select(HeadOfficeDirectorate).order_by(HeadOfficeDirectorate.name)
    )
    directorates = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "name": d.name,
            "code": d.code
        }
        for d in directorates
    ]

@router.get("/directorates/{directorate_id}")
async def get_directorate(
    directorate_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get a specific directorate by ID.
    """
    result = await session.execute(
        select(HeadOfficeDirectorate).where(HeadOfficeDirectorate.id == directorate_id)
    )
    directorate = result.scalar_one_or_none()

    if not directorate:
        raise HTTPException(status_code=404, detail="Directorate not found")

    # Get device count for this directorate
    count_result = await session.execute(
        select(func.count()).select_from(Device).where(
            Device.directorate_id == directorate_id,
            Device.is_active == True
        )
    )
    device_count = count_result.scalar() or 0

    return {
        "id": str(directorate.id),
        "name": directorate.name,
        "code": directorate.code,
        "device_count": device_count
    }

@router.post("/directorates")
async def create_directorate(
    directorate_data: DirectorateCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new Head Office Directorate.
    """
    # Check if name already exists
    result = await session.execute(
        select(HeadOfficeDirectorate).where(HeadOfficeDirectorate.name == directorate_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Directorate with this name already exists")

    directorate = HeadOfficeDirectorate(
        id=str(uuid.uuid4()),
        name=directorate_data.name,
        code=directorate_data.code
    )

    session.add(directorate)
    await session.commit()
    await session.refresh(directorate)

    return {
        "message": "Directorate created successfully",
        "directorate": {
            "id": str(directorate.id),
            "name": directorate.name,
            "code": directorate.code
        }
    }

@router.put("/directorates/{directorate_id}")
async def update_directorate(
    directorate_id: str,
    directorate_data: DirectorateUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update an existing directorate.
    """
    result = await session.execute(
        select(HeadOfficeDirectorate).where(HeadOfficeDirectorate.id == directorate_id)
    )
    directorate = result.scalar_one_or_none()

    if not directorate:
        raise HTTPException(status_code=404, detail="Directorate not found")

    update_data = directorate_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(directorate, key, value)

    await session.commit()
    await session.refresh(directorate)

    return {
        "message": "Directorate updated successfully",
        "directorate": {
            "id": str(directorate.id),
            "name": directorate.name,
            "code": directorate.code
        }
    }

@router.delete("/directorates/{directorate_id}")
async def delete_directorate(
    directorate_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a directorate (only if no devices are assigned).
    """
    result = await session.execute(
        select(HeadOfficeDirectorate).where(HeadOfficeDirectorate.id == directorate_id)
    )
    directorate = result.scalar_one_or_none()

    if not directorate:
        raise HTTPException(status_code=404, detail="Directorate not found")

    # Check if devices are assigned
    count_result = await session.execute(
        select(func.count()).select_from(Device).where(
            Device.directorate_id == directorate_id,
            Device.is_active == True
        )
    )
    device_count = count_result.scalar() or 0

    if device_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete directorate with {device_count} active devices assigned"
        )

    await session.delete(directorate)
    await session.commit()

    return {"message": f"Directorate '{directorate.name}' deleted successfully"}

# ============================================================================
# Agent Endpoints (full CRUD, with is_active + branch_id + directorate_id support)
# ============================================================================

@router.get("/agents")
async def get_agents(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    branch_id: Optional[str] = None,
    directorate_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Get all agents with optional role/status/branch/directorate filtering.
    """
    query = select(Agent)
    if role:
        query = query.where(Agent.role == role)
    if is_active is not None:
        query = query.where(Agent.is_active == is_active)
    if branch_id:
        query = query.where(Agent.branch_id == branch_id)
    if directorate_id:
        query = query.where(Agent.directorate_id == directorate_id)

    result = await session.execute(query.order_by(Agent.full_name))
    agents = result.scalars().all()

    return {
        "agents": [
            {
                "id": str(a.id),
                "full_name": a.full_name,
                "role": a.role,
                "email": a.email,
                "phone_number": a.phone_number,
                "branch_id": str(a.branch_id) if a.branch_id else None,
                "directorate_id": str(a.directorate_id) if a.directorate_id else None,
                "is_active": a.is_active
            }
            for a in agents
        ]
    }

@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed information for a single agent.
    """
    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    ticket_result = await session.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.assigned_agent_id == agent.id,
            Ticket.status.in_(["OPEN", "ACKNOWLEDGED"])
        )
    )
    open_ticket_count = ticket_result.scalar() or 0

    return {
        "id": str(agent.id),
        "full_name": agent.full_name,
        "role": agent.role,
        "email": agent.email,
        "phone_number": agent.phone_number,
        "branch_id": str(agent.branch_id) if agent.branch_id else None,
        "directorate_id": str(agent.directorate_id) if agent.directorate_id else None,
        "is_active": agent.is_active,
        "open_tickets": open_ticket_count
    }

@router.post("/agents")
async def create_agent(
    agent_data: AgentCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new agent.
    """
    result = await session.execute(
        select(Agent).where(Agent.email == agent_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent with this email already exists")

    # Validate: Must have either branch_id OR directorate_id, not both
    if not agent_data.branch_id and not agent_data.directorate_id:
        raise HTTPException(status_code=400, detail="Agent must belong to either a Branch or a Directorate")
    if agent_data.branch_id and agent_data.directorate_id:
        raise HTTPException(status_code=400, detail="Agent cannot belong to both a Branch and a Directorate")

    agent = Agent(
        full_name=agent_data.full_name,
        role=agent_data.role,
        email=agent_data.email,
        phone_number=agent_data.phone_number,
        branch_id=agent_data.branch_id,
        directorate_id=agent_data.directorate_id,
        is_active=agent_data.is_active
    )

    session.add(agent)
    await session.commit()
    await session.refresh(agent)

    return {
        "message": "Agent created successfully",
        "agent": {
            "id": str(agent.id),
            "full_name": agent.full_name,
            "role": agent.role,
            "email": agent.email,
            "phone_number": agent.phone_number,
            "branch_id": str(agent.branch_id) if agent.branch_id else None,
            "directorate_id": str(agent.directorate_id) if agent.directorate_id else None,
            "is_active": agent.is_active
        }
    }

@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Full update of an existing agent.
    """
    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = agent_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    await session.commit()
    await session.refresh(agent)

    return {
        "message": "Agent updated successfully",
        "agent": {
            "id": str(agent.id),
            "full_name": agent.full_name,
            "role": agent.role,
            "email": agent.email,
            "phone_number": agent.phone_number,
            "branch_id": str(agent.branch_id) if agent.branch_id else None,
            "directorate_id": str(agent.directorate_id) if agent.directorate_id else None,
            "is_active": agent.is_active
        }
    }

@router.patch("/agents/{agent_id}")
async def patch_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Partially update an agent.
    """
    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = agent_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    await session.commit()
    await session.refresh(agent)

    return {
        "message": "Agent updated successfully",
        "agent": {
            "id": str(agent.id),
            "full_name": agent.full_name,
            "role": agent.role,
            "email": agent.email,
            "phone_number": agent.phone_number,
            "branch_id": str(agent.branch_id) if agent.branch_id else None,
            "directorate_id": str(agent.directorate_id) if agent.directorate_id else None,
            "is_active": agent.is_active
        }
    }

@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Soft-delete an agent (sets is_active=False).
    """
    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    ticket_result = await session.execute(
        select(Ticket).where(Ticket.assigned_agent_id == agent.id)
    )
    for ticket in ticket_result.scalars().all():
        ticket.assigned_agent_id = None

    agent.is_active = False
    await session.commit()

    return {"message": f"Agent '{agent.full_name}' deactivated successfully"}

# ============================================================================
# Dashboard Summary Endpoint
# ============================================================================

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_db)
):
    """
    Get dashboard summary statistics.
    """
    total_result = await session.execute(
        select(func.count()).select_from(Device).where(Device.is_active == True)
    )
    total_devices = total_result.scalar() or 0

    # Get latest status for each device
    subquery = select(
        DeviceStatusLog.device_id,
        func.max(DeviceStatusLog.recorded_at).label("max_recorded")
    ).group_by(DeviceStatusLog.device_id).subquery()

    status_query = select(DeviceStatusLog.status, func.count()).join(
        subquery,
        and_(
            DeviceStatusLog.device_id == subquery.c.device_id,
            DeviceStatusLog.recorded_at == subquery.c.max_recorded
        )
    ).group_by(DeviceStatusLog.status)

    status_result = await session.execute(status_query)
    status_counts = {row[0]: row[1] for row in status_result.all()}

    ticket_result = await session.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.status.in_(["OPEN", "ACKNOWLEDGED"])
        )
    )
    open_tickets = ticket_result.scalar() or 0

    critical_result = await session.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.status.in_(["OPEN", "ACKNOWLEDGED"]),
            Ticket.severity == "CRITICAL"
        )
    )
    critical_tickets = critical_result.scalar() or 0

    return {
        "total_devices": total_devices,
        "devices_status": {
            "UP": status_counts.get("UP", 0),
            "DOWN": status_counts.get("DOWN", 0),
            "UNSTABLE": status_counts.get("UNSTABLE", 0),
            "UNKNOWN": total_devices - status_counts.get("UP", 0) - status_counts.get("DOWN", 0) - status_counts.get("UNSTABLE", 0)
        },
        "open_tickets": open_tickets,
        "critical_tickets": critical_tickets,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# ============================================================================
# Uptime Report Endpoint
# ============================================================================

@router.get("/dashboard/uptime")
async def get_uptime_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db)
):
    """
    Get uptime statistics for the last N days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    query = text("""
        SELECT
            d.id,
            d.hostname,
            COUNT(CASE WHEN l.status = 'UP' THEN 1 END) * 1.0 / COUNT(*) * 100 as uptime_percent
        FROM devices d
        JOIN device_status_log l ON d.id = l.device_id
        WHERE l.recorded_at >= :start_date
        AND d.is_active = true
        GROUP BY d.id, d.hostname
    """)

    result = await session.execute(query, {"start_date": start_date})
    stats = result.all()

    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "devices": [
            {
                "device_id": str(row[0]),
                "hostname": row[1],
                "uptime_percent": round(row[2], 2)
            }
            for row in stats
        ]
    }

# ============================================================================
# Topology Endpoint
# ============================================================================

@router.get("/topology")
async def get_topology(
    session: AsyncSession = Depends(get_db)
):
    """
    Get network topology data (nodes and links).
    """
    result = await session.execute(
        select(Device).where(Device.is_active == True)
    )
    devices = result.scalars().all()

    branch_result = await session.execute(select(Branch))
    branches = branch_result.scalars().all()

    nodes = []
    links = []
    device_map = {}
    branch_map = {b.id: b for b in branches}

    # Create device nodes
    for device in devices:
        branch_name = branch_map.get(device.branch_id).name if device.branch_id in branch_map else None

        device_map[str(device.id)] = {
            "id": str(device.id),
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "criticality": device.criticality,
            "vlan_id": device.vlan_id,
            "branch_id": str(device.branch_id) if device.branch_id else None,
            "branch_name": branch_name,
            "parent_switch_id": str(device.parent_switch_id) if device.parent_switch_id else None
        }

    # Get latest status for each device
    for device_id, data in device_map.items():
        status_query = select(DeviceStatusLog).where(
            DeviceStatusLog.device_id == device_id
        ).order_by(desc(DeviceStatusLog.recorded_at)).limit(1)
        status_result = await session.execute(status_query)
        latest = status_result.scalar_one_or_none()
        data["status"] = latest.status if latest else "UNKNOWN"

    # Create nodes list
    for device_id, data in device_map.items():
        nodes.append(data)

    # Create links based on parent_switch_id
    for device_id, data in device_map.items():
        if data["parent_switch_id"]:
            links.append({
                "source": data["parent_switch_id"],
                "target": data["id"],
                "type": "network"
            })

    # Add VLAN group nodes
    vlan_map = {}
    for device_id, data in device_map.items():
        if data["vlan_id"] and data["vlan_id"] not in vlan_map:
            vlan_map[data["vlan_id"]] = {
                "id": f"vlan-{data['vlan_id']}",
                "name": f"VLAN {data['vlan_id']}",
                "ip": f"VLAN {data['vlan_id']}",
                "device_type": "VLAN",
                "criticality": "MEDIUM",
                "vlan_id": data["vlan_id"],
                "status": "UNKNOWN",
                "is_vlan": True
            }

    for vlan_id, vlan_data in vlan_map.items():
        nodes.append(vlan_data)

        for device_id, data in device_map.items():
            if data["vlan_id"] == vlan_id and data["device_type"] == "SWITCH":
                links.append({
                    "source": data["id"],
                    "target": vlan_data["id"],
                    "type": "vlan"
                })

            if data["vlan_id"] == vlan_id and data["device_type"] != "SWITCH":
                links.append({
                    "source": vlan_data["id"],
                    "target": data["id"],
                    "type": "vlan-member"
                })

    # Add branch nodes
    for branch in branches:
        branch_node = {
            "id": f"branch-{str(branch.id)}",
            "name": branch.name,
            "ip": branch.wan_gateway_ip,
            "device_type": "BRANCH",
            "criticality": "LOW",
            "status": "UNKNOWN",
            "is_branch": True
        }
        nodes.append(branch_node)

        # Link branches to devices
        for device_id, data in device_map.items():
            if data["branch_id"] == str(branch.id):
                links.append({
                    "source": branch_node["id"],
                    "target": data["id"],
                    "type": "branch"
                })

    return {
        "nodes": nodes,
        "links": links,
        "total_devices": len(devices),
        "total_branches": len(branches),
        "total_vlans": len(vlan_map)
    }