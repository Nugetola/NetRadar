"""Standalone, testable reachability and root-cause diagnostics.

Implements the 5-stage sequence:
  1. Gateway/Switch Triangulation (SNMP)   -> switch_port_status()
  2. Port & Protocol Scan (TCP 135/445/22) -> _tcp_open()
  3. SNMP remote-alive check               -> device_snmp_alive()
  4. Packet-loss / latency analysis        -> _ping_stats()
  5. Traceroute (TTL triangulation)        -> _traceroute()
Plus an optional DNS-service check for devices flagged as DNS servers.
"""
import asyncio
import platform
import re
import subprocess
from datetime import datetime, timezone
from .config import get_settings
from .snmp_client import device_snmp_alive, switch_port_status

_IS_WINDOWS = platform.system().lower().startswith("win")
_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:packet\s*)?loss", re.IGNORECASE)
_AVG_RE_LINUX = re.compile(r"=\s*[\d.]+/([\d.]+)/")
_AVG_RE_WIN = re.compile(r"Average\s*=\s*(\d+)\s*ms", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


async def _command(*args: str, timeout: int) -> tuple[int, str]:
    """Run a short OS diagnostic in a worker thread (safe under any event loop policy)."""
    def run() -> tuple[int, str]:
        completed = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout + 2, check=False, text=True, encoding="utf-8", errors="replace",
        )
        return completed.returncode, completed.stdout
    try:
        return await asyncio.to_thread(run)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


async def _tcp_open(host: str, port: int, timeout: int = 2) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _ping_stats(target_ip: str, timeout: int, count: int = 4) -> dict:
    """Stage 4: send several probes and read packet loss / average latency from the
    summary line, instead of trusting a single echo — this is what separates rising
    congestion (partial loss) from a hard disconnect (100% loss)."""
    args = (
        ("ping", "-n", str(count), "-w", str(timeout * 1000), target_ip) if _IS_WINDOWS
        else ("ping", "-c", str(count), "-i", "0.3", "-W", str(timeout), target_ip)
    )
    code, output = await _command(*args, timeout=timeout * count)
    loss_match = _LOSS_RE.search(output)
    avg_match = (_AVG_RE_WIN if _IS_WINDOWS else _AVG_RE_LINUX).search(output)
    loss_percent = float(loss_match.group(1)) if loss_match else (100.0 if code != 0 else 0.0)
    avg_latency_ms = float(avg_match.group(1)) if avg_match else None
    return {"success": loss_percent < 100.0, "packet_loss_percent": loss_percent, "avg_latency_ms": avg_latency_ms, "raw": output[-500:]}


async def _traceroute(target_ip: str, timeout: int, max_hops: int = 15) -> str | None:
    """Stage 5: identify the last hop that actually responded, to localize the failure
    to the local switch, the WAN link, or the target node itself."""
    args = (
        ("tracert", "-h", str(max_hops), "-w", str(timeout * 1000), target_ip) if _IS_WINDOWS
        else ("traceroute", "-m", str(max_hops), "-w", str(timeout), target_ip)
    )
    _, output = await _command(*args, timeout=timeout * max_hops + 5)
    last_ip = None
    for line in output.splitlines():
        if "*" in line and not _IP_RE.search(line):
            continue
        match = _IP_RE.search(line)
        if match:
            last_ip = match.group(0)
    return last_ip


async def check_dns_service(dns_server_ip: str, test_hostname: str, timeout: int = 3) -> dict:
    """DNS-specific failure mode: distinguish a dead DNS *server* from a dead DNS *service*.
    If the server IP itself doesn't answer ICMP, report DNS_SERVER_DOWN; if it's reachable
    but won't resolve, report DNS_SERVICE_STOPPED."""
    server_up = (await _ping_stats(dns_server_ip, timeout, count=1))["success"]
    if not server_up:
        return {"dns_resolution": "DNS_SERVER_DOWN", "detail": "DNS server host is unreachable."}
    args = ("nslookup", test_hostname, dns_server_ip) if _IS_WINDOWS else ("dig", f"@{dns_server_ip}", test_hostname, "+time=2", "+tries=1")
    code, output = await _command(*args, timeout=timeout)
    resolved = code == 0 and ("Address" in output or "ANSWER SECTION" in output) and "NXDOMAIN" not in output and "server can't find" not in output
    return {
        "dns_resolution": "SUCCESSFUL" if resolved else "DNS_SERVICE_STOPPED",
        "detail": "Hostname resolved via this server." if resolved else "Server host answers ICMP but did not resolve the test hostname; DNS service on it is likely stopped.",
    }


async def run_diagnostics(
    target_ip: str,
    gateway_ip: str | None = None,
    *,
    switch_ip: str | None = None,
    switch_port_ifindex: int | None = None,
    snmp_community: str | None = None,
    dns_check_hostname: str | None = None,
) -> dict:
    """Return the canonical diagnostics payload for a stable, assigned IP address.

    switch_ip/switch_port_ifindex/snmp_community are resolved by the caller (monitor.py)
    from the device's parent switch and its VlanProfile — this module stays credential-free
    and network-topology-free by design, per the security/VLAN policy in the README.
    """
    settings = get_settings()
    timeout = settings.ping_timeout_seconds

    ping = await _ping_stats(target_ip, timeout)
    ports = await asyncio.gather(*(_tcp_open(target_ip, port) for port in (135, 445, 22)))
    reachable_ports = [port for port, open_ in zip((135, 445, 22), ports) if open_]

    root_cause: dict = {
        "target_ip": target_ip, "gateway_ip": gateway_ip,
        "packet_loss_percent": ping["packet_loss_percent"], "avg_latency_ms": ping["avg_latency_ms"],
        "tcp_open_ports": reachable_ports, "switch_ip": switch_ip, "switch_port": switch_port_ifindex,
        "port_status": "UNKNOWN", "snmp_agent_responding": None, "traceroute_stop_hop": None,
        "dns_resolution": "NOT_TESTED", "observed_at": datetime.now(timezone.utc).isoformat(),
        "ping_output": ping["raw"],
    }

    # DNS-server devices get a dedicated check that overrides the generic reachability path.
    if dns_check_hostname:
        dns_result = await check_dns_service(target_ip, dns_check_hostname, timeout)
        root_cause["dns_resolution"] = dns_result["dns_resolution"]
        if dns_result["dns_resolution"] != "SUCCESSFUL":
            root_cause["traceroute_stop_hop"] = await _traceroute(target_ip, timeout)
            return {"ping_status": "FAILED" if dns_result["dns_resolution"] == "DNS_SERVER_DOWN" else "PARTIAL",
                    "failure_reason": dns_result["dns_resolution"], "details": dns_result["detail"], "root_cause_analysis": root_cause}

    if ping["success"] and ping["packet_loss_percent"] == 0:
        root_cause["dns_resolution"] = "NOT_TESTED"
        return {"ping_status": "SUCCESS", "failure_reason": None,
                "details": "ICMP response received from assigned static IP.", "root_cause_analysis": root_cause}

    if 0 < ping["packet_loss_percent"] < 100:
        return {"ping_status": "PARTIAL", "failure_reason": "RISING_PACKET_LOSS",
                "details": f"{ping['packet_loss_percent']:.0f}% loss over 4 probes — consistent with network congestion rather than a hard disconnect.",
                "root_cause_analysis": root_cause}

    # Full loss (100%) — walk the remaining stages to localize the cause.
    snmp = await device_snmp_alive(target_ip, snmp_community, timeout) if snmp_community else {"snmp_agent_responding": None}
    root_cause["snmp_agent_responding"] = snmp.get("snmp_agent_responding")

    if reachable_ports or snmp.get("snmp_agent_responding"):
        details = f"ICMP failed but {'TCP ' + str(reachable_ports) if reachable_ports else ''}{' and ' if reachable_ports and snmp.get('snmp_agent_responding') else ''}{'SNMP agent responded' if snmp.get('snmp_agent_responding') else ''}; host is up and ICMP is likely blocked at the firewall."
        return {"ping_status": "FAILED", "failure_reason": "ICMP_BLOCKED", "details": details, "root_cause_analysis": root_cause}

    if switch_ip and switch_port_ifindex is not None and snmp_community:
        port_info = await switch_port_status(switch_ip, snmp_community, switch_port_ifindex, timeout)
        root_cause["port_status"] = port_info.get("port_status", "UNKNOWN")
        if port_info.get("reachable") and port_info["port_status"] in {"DOWN", "LOWER_LAYER_DOWN"}:
            root_cause["traceroute_stop_hop"] = await _traceroute(target_ip, timeout)
            return {"ping_status": "FAILED", "failure_reason": "CABLE_FAILURE",
                    "details": f"Switch reports port {switch_port_ifindex} as {port_info['port_status']} (no carrier) — cable or transceiver fault.",
                    "root_cause_analysis": root_cause}
        if port_info.get("reachable") and port_info["port_status"] == "UP":
            return {"ping_status": "FAILED", "failure_reason": "NIC_OR_STATIC_IP_FAULT",
                    "details": "Switch port is UP but the device does not answer ICMP, TCP, or SNMP — likely NIC failure, driver fault, or the assigned static IP/config was lost.",
                    "root_cause_analysis": root_cause}

    gateway_reachable = None
    if gateway_ip:
        gateway_reachable = (await _ping_stats(gateway_ip, timeout, count=1))["success"]
    root_cause["gateway_reachable"] = gateway_reachable
    if gateway_ip and not gateway_reachable:
        root_cause["traceroute_stop_hop"] = await _traceroute(target_ip, timeout)
        return {"ping_status": "FAILED", "failure_reason": "GATEWAY_OR_SEGMENT_DOWN",
                "details": "Target and its configured gateway are both unreachable; investigate the VLAN gateway, WAN link, or parent switch.",
                "root_cause_analysis": root_cause}

    root_cause["traceroute_stop_hop"] = await _traceroute(target_ip, timeout)
    return {"ping_status": "FAILED", "failure_reason": "CABLE_OR_NIC_DISCONNECT",
            "details": "No ICMP, TCP, or SNMP response, and the gateway is reachable. Confirm switch-port carrier/errors and the assigned static IP; an APIPA address or lost static IP is a NIC/configuration fault.",
            "root_cause_analysis": root_cause}