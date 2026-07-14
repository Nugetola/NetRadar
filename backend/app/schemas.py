from datetime import datetime
from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    hostname: str = Field(min_length=1, max_length=100)
    ip_address: str
    device_type: str = "PC"
    criticality: str = "MEDIUM"
    branch_id: str | None = None
    parent_switch_id: str | None = None
    vlan_id: int | None = None
    subnet: str | None = None


class DeviceView(DeviceCreate):
    id: str
    current_status: str
    failure_count: int

    model_config = {"from_attributes": True}


class Diagnostics(BaseModel):
    ping_status: str
    failure_reason: str | None = None
    details: str
    root_cause_analysis: dict


class StatusEvent(BaseModel):
    event_type: str = "DEVICE_STATUS_CHANGE"
    timestamp: datetime
    device_info: dict
    diagnostics: Diagnostics
    impact_level: str


class AgentCreate(BaseModel):
    full_name: str
    role: str
    email: str | None = None
    phone_number: str | None = None
    branch_id: str | None = None


class AgentView(AgentCreate):
    id: str
    is_active: bool
    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str


class BranchCreate(BaseModel):
    name: str
    region: str | None = None
    wan_gateway_ip: str | None = None


class VlanProfileCreate(BaseModel):
    vlan_id: int
    subnet: str | None = None
    gateway_ip: str | None = None
    snmp_version: str = "v3"
    snmp_credential_ref: str | None = None
