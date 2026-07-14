"""Standalone, testable reachability and first-pass root-cause diagnostics."""
import asyncio
import platform
import subprocess
from datetime import datetime, timezone
from .config import get_settings


async def _command(*args: str, timeout: int) -> tuple[int, str]:
    """Run a short OS diagnostic without requiring asyncio subprocess support.

    Some Windows server configurations use a selector event loop, which cannot
    create asyncio subprocess transports.  ``subprocess.run`` in a worker
    thread keeps the FastAPI event loop free and works with either policy.
    """
    def run() -> tuple[int, str]:
        completed = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout + 2,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return completed.returncode, completed.stdout

    try:
        return await asyncio.to_thread(run)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


async def _tcp_open(host: str, port: int, timeout: int = 2) -> bool:
    try:
        writer = None
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def run_diagnostics(target_ip: str, gateway_ip: str | None = None) -> dict:
    """Return the canonical diagnostics payload for a stable, assigned IP address."""
    settings = get_settings()
    is_windows = platform.system().lower().startswith("win")
    ping_args = ("ping", "-n", "1", "-w", str(settings.ping_timeout_seconds * 1000), target_ip) if is_windows else ("ping", "-c", "1", "-W", str(settings.ping_timeout_seconds), target_ip)
    code, ping_output = await _command(*ping_args, timeout=settings.ping_timeout_seconds)
    ping_ok = code == 0
    ports = await asyncio.gather(*(_tcp_open(target_ip, port) for port in (135, 445, 22)))
    reachable_ports = [port for port, open_ in zip((135, 445, 22), ports) if open_]
    gateway_reachable = None
    if gateway_ip:
        gateway_code, _ = await _command(*( ("ping", "-n", "1", "-w", str(settings.ping_timeout_seconds * 1000), gateway_ip) if is_windows else ("ping", "-c", "1", "-W", str(settings.ping_timeout_seconds), gateway_ip) ), timeout=settings.ping_timeout_seconds)
        gateway_reachable = gateway_code == 0

    if ping_ok:
        reason, details, status = None, "ICMP response received from assigned static IP.", "SUCCESS"
    elif reachable_ports:
        reason, details, status = "ICMP_BLOCKED", f"ICMP failed but TCP ports {reachable_ports} responded; host is reachable and ICMP is likely blocked.", "FAILED"
    elif gateway_reachable is False:
        reason, details, status = "GATEWAY_OR_SEGMENT_DOWN", "Target and its configured gateway are unreachable; investigate VLAN gateway, WAN, or parent switch.", "FAILED"
    else:
        reason, details, status = "CABLE_OR_NIC_DISCONNECT", "No ICMP or tested TCP service responded. Confirm switch-port carrier/errors and the assigned static IP; APIPA/lost static IP is a NIC/configuration fault.", "FAILED"

    return {
        "ping_status": status,
        "failure_reason": reason,
        "details": details,
        "root_cause_analysis": {
            "target_ip": target_ip, "gateway_ip": gateway_ip, "gateway_reachable": gateway_reachable,
            "tcp_open_ports": reachable_ports, "switch_port": None, "port_status": "UNKNOWN",
            "traceroute_stop_hop": None, "dns_resolution": "NOT_TESTED",
            "observed_at": datetime.now(timezone.utc).isoformat(), "ping_output": ping_output[-500:],
        },
    }
