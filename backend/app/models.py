import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import CIDR, INET, JSONB


# ============================================================================
# DATABASE TYPES
# ============================================================================

JsonPayload = JSON().with_variant(JSONB, "postgresql")

IpAddress = String(45).with_variant(
    INET,
    "postgresql"
)

Network = String(43).with_variant(
    CIDR,
    "postgresql"
)


# ============================================================================
# BASE
# ============================================================================

class Base(DeclarativeBase):
    pass


# ============================================================================
# BRANCH
# ============================================================================

class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    # Short unique code, e.g. "ADA", "HOB" — useful for display/reporting.
    code: Mapped[str | None] = mapped_column(
        String(10),
        unique=True,
        nullable=True
    )

    region: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    wan_gateway_ip: Mapped[str | None] = mapped_column(
        IpAddress,
        nullable=True
    )

    # RELATIONSHIPS
    devices: Mapped[list["Device"]] = relationship(
        "Device",
        back_populates="branch",
        cascade="all, delete-orphan"
    )

    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="branch"
    )


# ============================================================================
# HEAD OFFICE DIRECTORATE
# ============================================================================

class HeadOfficeDirectorate(Base):
    """
    Directorates / Offices under the Head Office (e.g. Information Technology
    Directorate, Chief Executive Office). These do NOT belong to a Branch —
    they are the Head Office side of the org structure.
    """

    __tablename__ = "head_office_directorates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False
    )

    # Short unique code, e.g. "ITD", "CEO"
    code: Mapped[str | None] = mapped_column(
        String(10),
        unique=True,
        nullable=True
    )

    # RELATIONSHIPS
    devices: Mapped[list["Device"]] = relationship(
        "Device",
        back_populates="directorate"
    )

    agents: Mapped[list["Agent"]] = relationship(
        "Agent",
        back_populates="directorate"
    )


# ============================================================================
# DEVICE
# ============================================================================

class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    hostname: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    ip_address: Mapped[str] = mapped_column(
        IpAddress,
        unique=True,
        index=True,
        nullable=False
    )

    branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.id"),
        nullable=True
    )

    # IMPORTANT:
    # This fixes:
    # 'Device' object has no attribute 'branch'
    branch: Mapped["Branch | None"] = relationship(
        "Branch",
        back_populates="devices"
    )

    directorate_id: Mapped[str | None] = mapped_column(
        ForeignKey("head_office_directorates.id"),
        nullable=True
    )

    directorate: Mapped["HeadOfficeDirectorate | None"] = relationship(
        "HeadOfficeDirectorate",
        back_populates="devices"
    )

    device_type: Mapped[str] = mapped_column(
        String(30),
        default="PC",
        nullable=False
    )

    criticality: Mapped[str] = mapped_column(
        String(10),
        default="MEDIUM",
        nullable=False
    )

    parent_switch_id: Mapped[str | None] = mapped_column(
        ForeignKey("devices.id"),
        nullable=True
    )

    # SELF-RELATIONSHIP
    parent_switch: Mapped["Device | None"] = relationship(
        "Device",
        remote_side="Device.id",
        foreign_keys=[parent_switch_id]
    )

    switch_port_ifindex: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    is_dns_server: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    vlan_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    subnet: Mapped[str | None] = mapped_column(
        Network,
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    current_status: Mapped[str] = mapped_column(
        String(10),
        default="UNKNOWN",
        nullable=False
    )

    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # STATUS HISTORY
    status_logs: Mapped[list["DeviceStatusLog"]] = relationship(
        "DeviceStatusLog",
        back_populates="device",
        cascade="all, delete-orphan"
    )

    # TICKETS
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="device",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "(branch_id IS NOT NULL AND directorate_id IS NULL) OR "
            "(branch_id IS NULL AND directorate_id IS NOT NULL)",
            name="ck_device_single_org_unit",
        ),
    )


# ============================================================================
# DEVICE STATUS LOG
# ============================================================================

class DeviceStatusLog(Base):
    __tablename__ = "device_status_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id"),
        index=True,
        nullable=False
    )

    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="status_logs"
    )

    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    failure_reason: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True
    )

    diagnostics: Mapped[dict] = mapped_column(
        JsonPayload,
        default=dict
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================================
# NOTIFICATION LOG
# ============================================================================

class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    payload: Mapped[dict] = mapped_column(
        JsonPayload,
        default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================================
# AGENT
# ============================================================================

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    email: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.id"),
        nullable=True
    )

    branch: Mapped["Branch | None"] = relationship(
        "Branch",
        back_populates="agents"
    )

    directorate_id: Mapped[str | None] = mapped_column(
        ForeignKey("head_office_directorates.id"),
        nullable=True
    )

    directorate: Mapped["HeadOfficeDirectorate | None"] = relationship(
        "HeadOfficeDirectorate",
        back_populates="agents"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="assigned_agent"
    )

    __table_args__ = (
        CheckConstraint(
            "(branch_id IS NOT NULL AND directorate_id IS NULL) OR "
            "(branch_id IS NULL AND directorate_id IS NOT NULL)",
            name="ck_agent_single_org_unit",
        ),
    )


# ============================================================================
# TICKET
# ============================================================================

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id"),
        index=True,
        nullable=False
    )

    device: Mapped["Device"] = relationship(
        "Device",
        back_populates="tickets"
    )

    severity: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="OPEN",
        nullable=False
    )

    escalation_level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )

    assigned_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id"),
        nullable=True
    )

    assigned_agent: Mapped["Agent | None"] = relationship(
        "Agent",
        back_populates="tickets"
    )

    sms_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    sms_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


# ============================================================================
# SERVICE HEARTBEAT
# ============================================================================

class ServiceHeartbeat(Base):
    __tablename__ = "service_heartbeat"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    instance_name: Mapped[str] = mapped_column(
        String(100),
        default="netradar-api"
    )

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )


# ============================================================================
# VLAN PROFILE
# ============================================================================

class VlanProfile(Base):
    """
    Per-VLAN monitoring policy.

    snmp_credential_ref:
    Reference to external secret store.
    Do not store SNMP passwords directly here.
    """

    __tablename__ = "vlan_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    vlan_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False
    )

    subnet: Mapped[str | None] = mapped_column(
        Network,
        nullable=True
    )

    gateway_ip: Mapped[str | None] = mapped_column(
        IpAddress,
        nullable=True
    )

    snmp_version: Mapped[str] = mapped_column(
        String(10),
        default="v3",
        nullable=False
    )

    snmp_credential_ref: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )


# ============================================================================
# AUDIT LOG
# ============================================================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    actor: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    metadata_json: Mapped[dict] = mapped_column(
        JsonPayload,
        default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )