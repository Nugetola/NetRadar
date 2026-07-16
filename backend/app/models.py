import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import CIDR, INET, JSONB

JsonPayload = JSON().with_variant(JSONB, "postgresql")
IpAddress = String(45).with_variant(INET, "postgresql")
Network = String(43).with_variant(CIDR, "postgresql")


class Base(DeclarativeBase):
    pass


class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    region: Mapped[str | None] = mapped_column(String(100))
    wan_gateway_ip: Mapped[str | None] = mapped_column(IpAddress)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hostname: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(IpAddress, unique=True, index=True, nullable=False)
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"))
    device_type: Mapped[str] = mapped_column(String(30), default="PC")
    criticality: Mapped[str] = mapped_column(String(10), default="MEDIUM")
    parent_switch_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"))
    switch_port_ifindex: Mapped[int | None] = mapped_column(Integer)  # SNMP ifIndex on parent_switch_id, for Stage 1 triangulation
    is_dns_server: Mapped[bool] = mapped_column(Boolean, default=False)  # enables the dedicated DNS-service check
    vlan_id: Mapped[int | None] = mapped_column(Integer)
    subnet: Mapped[str | None] = mapped_column(Network)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_status: Mapped[str] = mapped_column(String(10), default="UNKNOWN")
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeviceStatusLog(Base):
    __tablename__ = "device_status_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(80))
    diagnostics: Mapped[dict] = mapped_column(JsonPayload, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JsonPayload, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # NETWORK_AGENT / SUPERVISOR / MANAGER
    email: Mapped[str | None] = mapped_column(String(100))
    phone_number: Mapped[str | None] = mapped_column(String(20))
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"))
    sms_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ServiceHeartbeat(Base):
    __tablename__ = "service_heartbeat"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_name: Mapped[str] = mapped_column(String(100), default="netradar-api")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VlanProfile(Base):
    """Per-VLAN monitoring policy; secret_ref points to an external secret store."""
    __tablename__ = "vlan_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vlan_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    subnet: Mapped[str | None] = mapped_column(Network)
    gateway_ip: Mapped[str | None] = mapped_column(IpAddress)
    snmp_version: Mapped[str] = mapped_column(String(10), default="v3")
    snmp_credential_ref: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JsonPayload, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())