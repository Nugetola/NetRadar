"""Minimal async SNMP GET helper (pysnmp v3arch asyncio).

Credentials policy: callers must resolve a VlanProfile.snmp_credential_ref
through the organization's secrets manager before calling this module.
`config.snmp_dev_community` exists only for local/dev testing against a lab
switch and must stay unset in production (see README SNMP profile policy).
"""
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData, ContextData, ObjectIdentity, ObjectType,
    SnmpEngine, UdpTransportTarget, get_cmd,
)

# Standard MIB-II OIDs used by the diagnostic engine.
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"   # + .<ifIndex>
OID_IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"    # + .<ifIndex>

IF_OPER_STATUS_LABELS = {"1": "UP", "2": "DOWN", "3": "TESTING", "7": "LOWER_LAYER_DOWN"}


async def snmp_get(ip: str, community: str, oid: str, timeout: int = 2, port: int = 161) -> tuple[str | None, str | None]:
    """Single SNMP v2c GET. Returns (value, error) — never raises for network failures."""
    engine = SnmpEngine()
    try:
        target = await UdpTransportTarget.create((ip, port), timeout=timeout, retries=0)
        error_indication, error_status, _, var_binds = await get_cmd(
            engine, CommunityData(community, mpModel=1), target, ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if error_indication:
            return None, str(error_indication)
        if error_status:
            return None, error_status.prettyPrint()
        return str(var_binds[0][1]), None
    except OSError as exc:
        return None, str(exc)
    finally:
        engine.transport_dispatcher.close_dispatcher() if getattr(engine, "transport_dispatcher", None) else None


async def switch_port_status(switch_ip: str, community: str, if_index: int, timeout: int = 2) -> dict:
    """Stage 1: query a specific switch interface's operational status and error counter."""
    status_raw, status_err = await snmp_get(switch_ip, community, f"{OID_IF_OPER_STATUS}.{if_index}", timeout)
    errors_raw, _ = await snmp_get(switch_ip, community, f"{OID_IF_IN_ERRORS}.{if_index}", timeout)
    if status_err:
        return {"reachable": False, "port_status": "UNKNOWN", "error": status_err}
    return {
        "reachable": True,
        "port_status": IF_OPER_STATUS_LABELS.get(status_raw, f"UNKNOWN({status_raw})"),
        "if_in_errors": errors_raw,
    }


async def device_snmp_alive(ip: str, community: str, timeout: int = 2) -> dict:
    """Stage 3: an SNMP agent reply proves the OS/network stack is up even if ICMP is blocked
    or the port scan came back empty — this is what actually distinguishes 'host is up but
    quiet' from 'host is powered off / OS hung'."""
    descr, err = await snmp_get(ip, community, OID_SYS_DESCR, timeout)
    if err:
        return {"snmp_agent_responding": False, "sys_descr": None}
    return {"snmp_agent_responding": True, "sys_descr": descr}