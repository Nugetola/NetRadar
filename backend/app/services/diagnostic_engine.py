"""
Diagnostic Engine

Uses:
- ICMP ping
- Gateway check
- TCP port scan
- Traceroute

SNMP is handled separately by SNMPService.
"""

import asyncio
import functools
import logging
import platform
import re
import subprocess

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


IS_WINDOWS = platform.system().lower() == "windows"


class DiagnosticEngine:
    """
    Root Cause Diagnostic Engine for OIC NetRadar.

    SNMP is intentionally NOT used here.
    SNMP polling is handled by SNMPService.

    NOTE: ping/traceroute use *synchronous* subprocess calls executed in a
    thread pool executor (loop.run_in_executor) instead of
    asyncio.create_subprocess_exec(). This avoids a Windows-specific issue
    where asyncio subprocess support requires the ProactorEventLoop, and
    (depending on Python/uvicorn version) that policy may silently not be
    honored, causing every ping/traceroute call to fail immediately with a
    bare `NotImplementedError` (which prints as an empty string).
    """

    def __init__(
        self,
        ping_count: int = 3,
        ping_timeout: int = 2,
    ):
        self.ping_count = ping_count
        self.ping_timeout = ping_timeout

        self.common_ports = {
            22: "SSH",
            135: "NetBIOS",
            445: "SMB",
            443: "HTTPS",
            3389: "RDP",
            80: "HTTP",
        }

    async def run_diagnostics(
        self,
        target_ip: str,
    ) -> Dict[str, Any]:
        """
        Run comprehensive diagnostics.
        """

        target_ip = str(target_ip)

        timestamp = datetime.utcnow().isoformat() + "Z"

        logger.info(f"🔍 Running diagnostics on {target_ip}")

        # -------------------------------------------------
        # STAGE 1: PING
        # -------------------------------------------------

        ping_result = await self._ping(target_ip)

        if ping_result["success"]:

            logger.info(f"✅ {target_ip} is UP (ping successful)")

            return {
                "event_type": "DEVICE_STATUS_CHANGE",
                "timestamp": timestamp,
                "device_info": {
                    "ip_address": target_ip,
                    "status": "UP",
                },
                "diagnostics": {
                    "ping_status": "SUCCESS",
                    "failure_reason": "NONE",
                    "details": "Device is responding to ICMP ping.",
                    "root_cause_analysis": {
                        "latency_ms": ping_result.get("latency", 0),
                        "packet_loss_percent": ping_result.get(
                            "packet_loss", 0
                        ),
                    },
                },
                "impact_level": "NONE",
            }

        logger.warning(
            f"⚠️ {target_ip} is DOWN - running diagnostic sequence"
        )

        # -------------------------------------------------
        # STAGE 2: GATEWAY
        # -------------------------------------------------

        gateway_result = await self._check_gateway(target_ip)

        # -------------------------------------------------
        # STAGE 3: PORT SCAN
        # -------------------------------------------------

        port_results = await self._port_scan(target_ip)

        # -------------------------------------------------
        # STAGE 4: TRACEROUTE
        # -------------------------------------------------

        traceroute_result = await self._traceroute(target_ip)

        # -------------------------------------------------
        # ROOT CAUSE
        # -------------------------------------------------

        failure_reason, details = self._determine_root_cause(
            ping_result,
            gateway_result,
            port_results,
            traceroute_result,
            target_ip,
        )

        diagnostic = {
            "event_type": "DEVICE_STATUS_CHANGE",
            "timestamp": timestamp,
            "device_info": {
                "ip_address": target_ip,
                "status": "DOWN",
            },
            "diagnostics": {
                "ping_status": "FAILED",
                "failure_reason": failure_reason,
                "details": details,
                "root_cause_analysis": {
                    "ping_packet_loss": ping_result.get(
                        "packet_loss", 100
                    ),
                    "gateway_reachable": gateway_result.get(
                        "reachable", False
                    ),
                    "gateway_ip": gateway_result.get(
                        "gateway_ip", "Unknown"
                    ),
                    "gateway_latency": gateway_result.get(
                        "gateway_latency", 0
                    ),
                    "responding_ports": port_results.get(
                        "responding_ports", []
                    ),
                    "any_port_responding": port_results.get(
                        "any_port_responding", False
                    ),
                    "traceroute_hops": traceroute_result.get(
                        "hops", []
                    ),
                    "traceroute_last_hop": traceroute_result.get(
                        "last_hop"
                    ),
                    "traceroute_stop_at": traceroute_result.get(
                        "stop_at"
                    ),
                },
            },
            "impact_level": self._determine_impact_level(failure_reason),
        }

        logger.info(
            f"🎯 Diagnostic complete for {target_ip}: {failure_reason}"
        )

        return diagnostic

    # =====================================================
    # SYNC SUBPROCESS HELPER (runs in a thread executor)
    # =====================================================

    @staticmethod
    def _run_subprocess_sync(
        cmd: List[str],
        timeout: float,
    ) -> Tuple[int, str, str]:
        """
        Blocking subprocess call, meant to be run via
        loop.run_in_executor(). Works identically on Windows and
        Linux/macOS and does NOT require ProactorEventLoop.
        """

        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )

            return (
                completed.returncode,
                completed.stdout.decode(errors="ignore"),
                completed.stderr.decode(errors="ignore"),
            )

        except subprocess.TimeoutExpired:
            raise

    async def _run_subprocess(
        self,
        cmd: List[str],
        timeout: float,
    ) -> Tuple[int, str, str]:
        loop = asyncio.get_running_loop()

        func = functools.partial(
            self._run_subprocess_sync,
            cmd,
            timeout,
        )

        return await loop.run_in_executor(None, func)

    # =====================================================
    # PING
    # =====================================================

    async def _ping(
        self,
        ip: str,
    ) -> Dict[str, Any]:

        ip = str(ip)

        try:

            if IS_WINDOWS:
                cmd = [
                    "ping",
                    "-n",
                    str(self.ping_count),
                    "-w",
                    str(self.ping_timeout * 1000),
                    ip,
                ]
            else:
                cmd = [
                    "ping",
                    "-c",
                    str(self.ping_count),
                    "-W",
                    str(self.ping_timeout),
                    "-q",
                    ip,
                ]

            returncode, output, _stderr = await self._run_subprocess(
                cmd,
                timeout=(self.ping_timeout * self.ping_count) + 5,
            )

            if returncode == 0:

                packet_loss = 0

                loss_match = re.search(
                    r"(\d+)%.*loss", output, re.IGNORECASE
                )

                if loss_match:
                    packet_loss = int(loss_match.group(1))

                latency = 0.0

                # Linux format
                avg_match = re.search(r"=\s*[\d.]+/([\d.]+)/", output)

                if avg_match:
                    latency = float(avg_match.group(1))
                else:
                    # Windows format
                    time_match = re.search(
                        r"time[=<](\d+\.?\d*)", output, re.IGNORECASE
                    )

                    if time_match:
                        latency = float(time_match.group(1))

                return {
                    "success": True,
                    "latency": round(latency, 2),
                    "packet_loss": packet_loss,
                }

            loss_match = re.search(
                r"(\d+)%.*loss", output, re.IGNORECASE
            )

            packet_loss = (
                int(loss_match.group(1)) if loss_match else 100
            )

            return {
                "success": False,
                "packet_loss": packet_loss,
                "error": output.strip()[:200] or "Ping failed",
            }

        except subprocess.TimeoutExpired:

            logger.warning(f"Ping timeout for {ip}")

            return {
                "success": False,
                "packet_loss": 100,
                "error": "Timeout",
            }

        except Exception as exc:

            logger.error(
                f"Ping error for {ip}: {exc!r}"
            )

            return {
                "success": False,
                "packet_loss": 100,
                "error": repr(exc) or "Unknown ping error",
            }

    # =====================================================
    # GATEWAY
    # =====================================================

    async def _check_gateway(
        self,
        target_ip: str,
    ) -> Dict[str, Any]:

        try:
            parts = str(target_ip).split(".")

            if len(parts) != 4:
                return {
                    "reachable": False,
                    "gateway_ip": "0.0.0.0",
                    "port_status": "UNKNOWN",
                }

            gateway_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.1"

            ping_result = await self._ping(gateway_ip)

            return {
                "reachable": ping_result["success"],
                "gateway_ip": gateway_ip,
                "port_status": (
                    "UP (ICMP only)"
                    if ping_result["success"]
                    else "DOWN"
                ),
                "gateway_latency": ping_result.get("latency", 0),
            }

        except Exception as exc:
            logger.error(f"Gateway check error: {exc!r}")

            return {
                "reachable": False,
                "gateway_ip": "0.0.0.0",
                "port_status": "UNKNOWN",
            }

    # =====================================================
    # PORT SCAN
    # =====================================================

    async def _port_scan(
        self,
        target_ip: str,
    ) -> Dict[str, Any]:

        target_ip = str(target_ip)

        async def check_port(port: int) -> Optional[int]:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target_ip, port),
                    timeout=2.0,
                )

                writer.close()

                try:
                    await writer.wait_closed()
                except Exception:
                    pass

                return port

            except Exception:
                return None

        tasks = [check_port(port) for port in self.common_ports]

        results = await asyncio.gather(*tasks)

        responding_ports = [
            port for port in results if port is not None
        ]

        port_names = [
            {"port": port, "service": self.common_ports[port]}
            for port in responding_ports
        ]

        return {
            "responding_ports": port_names,
            "any_port_responding": bool(responding_ports),
        }

    # =====================================================
    # TRACEROUTE
    # =====================================================

    async def _traceroute(
        self,
        target_ip: str,
        max_hops: int = 15,
    ) -> Dict[str, Any]:

        target_ip = str(target_ip)

        try:
            if IS_WINDOWS:
                cmd = [
                    "tracert",
                    "-d",
                    "-h",
                    str(max_hops),
                    "-w",
                    "2000",
                    target_ip,
                ]
            else:
                cmd = [
                    "traceroute",
                    "-n",
                    "-m",
                    str(max_hops),
                    "-w",
                    "2",
                    "-q",
                    "1",
                    target_ip,
                ]

            _returncode, output, _stderr = await self._run_subprocess(
                cmd,
                timeout=30,
            )

            hops = []

            for line in output.splitlines():
                match = re.match(
                    r"\s*(\d+)\s+([0-9.]+|\*)", line
                )

                if match:
                    hop_num = int(match.group(1))
                    hop_ip = match.group(2)

                    hops.append({"hop": hop_num, "ip": hop_ip})

            reached_target = target_ip in [
                hop["ip"] for hop in hops if hop["ip"] != "*"
            ]

            last_reachable = None

            for hop in reversed(hops):
                if hop["ip"] != "*":
                    last_reachable = hop["ip"]
                    break

            stop_at = None

            if not reached_target and last_reachable:
                stop_at = last_reachable

            return {
                "hops": hops,
                "last_hop": last_reachable,
                "stop_at": stop_at,
                "reached_target": reached_target,
            }

        except subprocess.TimeoutExpired:
            return {
                "hops": [],
                "last_hop": None,
                "stop_at": target_ip,
                "reached_target": False,
            }

        except Exception as exc:
            logger.error(f"Traceroute error: {exc!r}")

            return {
                "hops": [],
                "last_hop": None,
                "stop_at": target_ip,
                "reached_target": False,
            }

    # =====================================================
    # ROOT CAUSE
    # =====================================================

    def _determine_root_cause(
        self,
        ping: Dict[str, Any],
        gateway: Dict[str, Any],
        ports: Dict[str, Any],
        traceroute: Dict[str, Any],
        target_ip: str,
    ) -> Tuple[str, str]:

        if not gateway.get("reachable", False):
            return (
                "VLAN_GATEWAY_DOWN",
                (
                    "VLAN gateway "
                    f"({gateway.get('gateway_ip', 'Unknown')}) "
                    "is unreachable."
                ),
            )

        if ports.get("any_port_responding", False) and not ping.get(
            "success", False
        ):
            return (
                "ICMP_BLOCKED",
                (
                    f"Device {target_ip} is operational but ICMP "
                    "is blocked."
                ),
            )

        if ping.get("packet_loss", 0) > 50:
            return (
                "NETWORK_CONGESTION",
                (
                    "High packet loss "
                    f"({ping.get('packet_loss')}%) detected."
                ),
            )

        if (
            traceroute.get("stop_at")
            and traceroute["stop_at"] != target_ip
        ):
            return (
                "LINK_FAILURE",
                (
                    "Network path fails at "
                    f"{traceroute['stop_at']}."
                ),
            )

        if traceroute.get(
            "reached_target", False
        ) and not ping.get("success", False):
            return (
                "DEVICE_UNRESPONSIVE",
                (
                    f"Device {target_ip} is reachable but not "
                    "responding to ICMP."
                ),
            )

        if not ping.get("success", False) and not ports.get(
            "any_port_responding", False
        ):
            return (
                "CABLE_FAILURE",
                f"Device {target_ip} is completely unresponsive.",
            )

        return (
            "UNKNOWN_FAILURE",
            f"Device {target_ip} is down but root cause unknown.",
        )

    # =====================================================
    # IMPACT
    # =====================================================

    def _determine_impact_level(
        self,
        failure_reason: str,
    ) -> str:

        critical_failures = {
            "VLAN_GATEWAY_DOWN",
            "CABLE_FAILURE",
            "LINK_FAILURE",
        }

        high_failures = {
            "DEVICE_UNRESPONSIVE",
            "NETWORK_CONGESTION",
        }

        if failure_reason in critical_failures:
            return "CRITICAL"

        if failure_reason in high_failures:
            return "HIGH"

        if failure_reason == "ICMP_BLOCKED":
            return "MEDIUM"

        return "LOW"